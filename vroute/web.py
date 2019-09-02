import asyncio
import logging

from aiohttp import web

from .db import Host, Address
from .util import WindowIterator
from . import VRoute
from .models import Addresses

log = logging.getLogger(__name__)


class Handlers:
    def __init__(self, app: VRoute):
        self.app = app
        self.lock = asyncio.Lock()

    def session(self):
        return self.app.new_session()

    async def add(self, request):
        """
        Adds new Host record and resolved addresses.
        If host already exists, renews addresses.
        """
        if not request.has_body:
            return web.json_response({"error": "Provide body"}, status=400)
        json = await request.json()
        host = json["host"]
        session = self.session()
        record = session.query(Host).filter(Host.name == host).first()
        already_exists = bool(record)
        if not already_exists:
            record = Host(name=host, comment=json.get("comment"))
            session.add(record)
            session.commit()
        addrs = await record.aresolve()
        session.add_all(addrs)
        session.commit()
        return web.json_response(
            {"exists": already_exists, "addrs": [x.value for x in addrs]}
        )

    async def remove(self, request):
        """ Removes host from the database. """
        json = await request.json()
        host = json["host"]
        session = self.session()
        host = session.query(Host).filter(Host.name == host).first()
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
        addresses = await Addresses.fromdb(session)
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
        try:
            while 1:
                log.info("Executing background sync...")
                await self.sync(None)
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            pass


def get_webapp(app, coroutines=False):
    handlers = Handlers(app)
    app = web.Application()
    if coroutines:
        app.on_startup.append(handlers.startup_tasks)
        app.on_cleanup.append(handlers.shutdown_tasks)
    router = app.router
    router.add_post("/", handlers.add)
    router.add_get("/", handlers.show)
    router.add_post("/rm", handlers.remove)
    router.add_post("/sync", handlers.sync)
    router.add_post("/purge", handlers.purge)
    return app
