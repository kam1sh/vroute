import asyncio
import itertools
import logging

from aiohttp import web
import aiodns.error
from sqlalchemy.orm.exc import NoResultFound

from .db import Host, Address
from .util import WindowIterator
from . import VRoute
from .models import Addresses

log = logging.getLogger(__name__)


def chunked(iterable, size):
    args = [iter(iterable)] * size
    return itertools.zip_longest(*args, fillvalue=None)


class Handlers:
    def __init__(self, app: VRoute):
        self.app = app
        self.lock = asyncio.Lock()

    def session(self):
        return self.app.new_session()

    async def add_host(self, request):
        """
        Adds new Host record and resolved addresses.
        If host already exists, renews addresses.
        """
        if not request.has_body:
            return web.json_response({"error": "Provide body"}, status=400)
        json = await request.json()
        host = json["host"]
        session = self.session()
        already_exists = True
        try:
            record = session.query(Host).filter(Host.name == host).one()
        except NoResultFound:
            already_exists = False
            record = Host(name=host, comment=json.get("comment"))
            session.add(record)
            session.commit()
        addrs = await record.aresolve()
        session.add_all(addrs)
        session.commit()
        return web.json_response(
            {"exists": already_exists, "addrs": [x.value for x in addrs]}
        )

    async def add_routes(self, request):
        if not request.has_body:
            return web.json_response({"error": "Provide body"}, status=400)
        json = await request.json()
        routes = json["routes"]
        session = self.session()
        exists = set()
        for chunk in chunked(routes, 100):
            addrs = session.query(Address.value)\
                .filter(Address.value.in_(chunk))\
                .filter(Address.host_id.is_(None))
            exists.update(addrs)

        response = {"exists": len(exists), "count": len(routes) - len(exists)}
        for item in filter(lambda x: x not in exists, routes):
            addr = Address(value=item)
            session.add(addr)
        session.commit()
        return web.json_response(response)

    async def remove(self, request):
        """ Removes host from the database. """
        json = await request.json()
        host = json["host"]
        session = self.session()
        host = session.query(Host).filter(Host.name == host).one()
        if host is None:
            return web.json_response({"error": "Host not found."}, status=404)
        log.info("Removing host %s", host.id)
        # TODO figure out why CASCADE doesn't work
        host.get_addresses(session).delete()
        session.delete(host)
        session.commit()
        return web.Response(status=204)

    async def show(self, request):
        """ Shows database contents. """
        session = self.session()
        gen = WindowIterator(session.query(Host))
        if not gen.has_any:
            return web.Response(status=204)
        output = {}
        for host in gen:
            addrs = session.query(Address).filter(Address.host_id == host.id)
            output[host.name] = {
                "comment": host.comment,
                "addrs": [addr.value for addr in addrs],
            }
        return web.json_response(output)

    async def sync(self, request):
        async with self.lock:
            return await self._sync(request)

    async def _sync(self, request):
        """ Synchronizes routing tables with database. """
        session = self.session()
        # Fetch all hosts and their IP addresses
        addresses = await Addresses.fromdb(session, ignorelist=self.app.cfg.get("exclude"))
        json = {}
        ipr = self.app.netlink
        # update routing information
        ipr.update()
        # Check routing rule and add if it doesn't exist
        ipr.check_rule()
        # Find what routes are up to date
        to_skip = addresses.what_to_skip(ipr.current)
        # Add new routes to the server routing table
        json["added"], json["skipped"] = ipr.add_all(addresses, to_skip)
        ros = self.app.ros
        if ros:
            ros.update()
            current = ros.get_routes()
            to_skip = addresses.what_to_skip(current)
            ros.add_routes(addresses, to_skip=to_skip)
            # addresses.add_routeros_routes(conn.api, ros_cfg=ros, to_skip=to_skip)
            json["full"] = True
        return web.json_response(json)

    async def purge(self, request):
        async with self.lock:
            return await self._purge(request)

    async def _purge(self, request):
        """ Removes routes that aren't present in the database. """
        session = self.session()
        addresses = await Addresses.fromdb(session)
        self.app.netlink.update()
        count = self.app.netlink.remove_outdated(keep=addresses)
        self.app.ros.update()
        ros_count = self.app.ros.remove_outdated(keep=addresses)
        return web.json_response({"removed": count, "removed_ros": ros_count})

    async def startup_tasks(self, app):
        app["sync"] = app.loop.create_task(self.background_sync())

    async def shutdown_tasks(self, app):
        app["sync"].cancel()
        await app["sync"]

    async def background_sync(self):
        while 1:
            try:
                log.info("Executing background sync...")
                await self.sync(None)
            except asyncio.CancelledError:
                return
            except:
                log.exception("Background sync error:")
            await asyncio.sleep(30)


def get_webapp(app, coroutines=False):
    handlers = Handlers(app)
    app = web.Application()
    if coroutines:
        app.on_startup.append(handlers.startup_tasks)
        app.on_cleanup.append(handlers.shutdown_tasks)
    router = app.router
    router.add_post("/", handlers.add_host)
    router.add_post("/routes", handlers.add_routes)
    router.add_get("/", handlers.show)
    router.add_post("/rm", handlers.remove)
    router.add_post("/sync", handlers.sync)
    router.add_post("/purge", handlers.purge)
    return app
