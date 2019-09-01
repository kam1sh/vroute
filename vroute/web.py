import logging
import asyncio

from aiohttp import web

from .db import Host, Address
from .util import WindowIterator
from . import routing
from .commands import resolve_hosts

log = logging.getLogger(__name__)


class Handlers:
    def __init__(self, app):
        self.app = app

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
        session.delete(host)
        session.commit()
        return web.Response(status=204)

    async def show(self, request):
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
        ipr = routing.RouteManager.fromconf(self.app.cfg)
        session = self.session()
        # Fetch all hosts and their IP addresses
        addresses = await resolve_hosts(session)
        json = {}
        with ipr:
            # Check routing rule and add if it doesn't exist
            ipr.check_rule()
            # Find what routes are up to date
            to_skip = addresses.what_to_skip(ipr.current)
            # Add new routes to the server routing table
            json["added"], json["skipped"] = ipr.add_all(addresses, to_skip)
        ros = self.app.cfg.get("routeros")
        if ros:
            with routing.RouterosManager.fromconf(ros) as conn:
                current = conn.get_routes()
                to_skip = addresses.what_to_skip(current)
                addresses.add_routeros_routes(conn.api, ros_cfg=ros, to_skip=to_skip)
            json["full"] = True
        return web.json_response(json)

    async def purge(self, request):
        try:
            ipr = routing.RouteManager.fromconf(self.app.cfg)
        except ValueError as e:
            return web.json_response({"error": str(e)}, status=500)
        session = self.session()
        addresses = await resolve_hosts(session)
        with ipr:
            current = ipr.get_routes()
            addresses.remove_outdated(current, ipr)
        # with routing.RouterosManager.fromconf(self.app.cfg["routeros"])


def get_webapp(app):
    handlers = Handlers(app)
    app = web.Application()
    router = app.router
    router.add_post("/", handlers.add)
    router.add_get("/", handlers.show)
    router.add_post("/rm", handlers.remove)
    router.add_post("/sync", handlers.sync)
    router.add_post("/purge", handlers.purge)
    return app
