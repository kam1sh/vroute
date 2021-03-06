import asyncio
import logging
import typing as ty

from sanic import Sanic as SanicBase
from sanic.response import json

# from .util import chunked, WindowIterator
# from .models import Addresses

log = logging.getLogger(__name__)


class Sanic(SanicBase):
    pass

app = Sanic()

@app.post("/sync")
async def sync(request):
    app = request.app
    exclude = app["cfg"].get("exclude")
    async with app["lock"]:
        return await _sync(session, exclude, app["netlink"], app["ros"])


async def _sync(session, exclude, ipr, ros):
    """ Synchronizes routing tables with database. """
    # Fetch all hosts and their IP addresses
    addresses = await Addresses.fromdb(session, ignorelist=exclude)
    json: ty.Dict[str, ty.Any] = {}
    result = ipr.sync(addresses)
    json.update(result)
    stats = ros.sync(addresses)
    json["routeros"] = stats
    return web.json_response(json)



async def startup_tasks(app):
    app["sync"] = app.loop.create_task(background_sync(app))


async def shutdown_tasks(app):
    app["sync"].cancel()
    await app["sync"]


async def background_sync(app):
    while 1:
        try:
            log.info("Executing background sync...")
            await _sync(
                app["vroute"].new_session(),
                app["cfg"].get("exclude"),
                app["netlink"],
                app["ros"],
            )
        except asyncio.CancelledError:
            return
        except:  # pylint:disable=bare-except
            log.exception("Background sync error:")
        await asyncio.sleep(600)


def get_webapp(app, coroutines=False):
    webapp = web.Application()
    webapp["vroute"] = app
    webapp["cfg"] = app.cfg
    webapp["netlink"] = app.netlink
    webapp["ros"] = app.ros
    webapp["lock"] = asyncio.Lock()
    if coroutines:
        webapp.on_startup.append(startup_tasks)
        webapp.on_cleanup.append(shutdown_tasks)
    webapp.add_routes(routes)
    return webapp



# @app.post("/")
# async def add_host(request):
#     """
#     Adds new Host record and resolved addresses.
#     If host already exists, renews addresses.
#     """
#     if not request.has_body:
#         return web.json_response({"error": "Provide body"}, status=400)
#     json = await request.json()
#     host = json["host"]
#     session = getsession(request)
#     already_exists = True
#     try:
#         record = session.query(Host).filter(Host.name == host).one()
#     except NoResultFound:
#         already_exists = False
#         record = Host(name=host, comment=json.get("comment"))
#         session.add(record)
#         session.commit()
#     addrs = await record.aresolve()
#     session.add_all(addrs)
#     session.commit()
#     return web.json_response(
#         {"exists": already_exists, "addrs": [x.value for x in addrs]}
#     )


@routes.post("/routes")
async def add_routes(request):
    if not request.has_body:
        return web.json_response({"error": "Provide body"}, status=400)
    json = await request.json()
    routes = json["routes"]
    session = getsession(request)
    exists: ty.Set[Address] = set()
    for chunk in chunked(routes, 100):
        addrs = (
            session.query(Address.value)
            .filter(Address.value.in_(chunk))
            .filter(Address.host_id.is_(None))
        )
        exists.update(addrs)

    response = {"exists": len(exists), "count": len(routes) - len(exists)}
    for item in filter(lambda x: x not in exists, routes):
        # noinspection PyArgumentList
        addr = Address(value=item)
        session.add(addr)
    session.commit()
    return web.json_response(response)


@routes.get("/")
async def show(request):
    """ Shows hosts with their addresses. """
    session = getsession(request)
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


@routes.post("/rm")
async def remove(request):
    """ Removes host from the database. """
    json = await request.json()
    host = json["host"]
    session = getsession(request)
    host = session.query(Host).filter(Host.name == host).one()
    if host is None:
        return web.json_response({"error": "Host not found."}, status=404)
    log.info("Removing host %s", host.id)
    # TODO figure out why CASCADE doesn't work
    host.get_addresses(session).delete()
    session.delete(host)
    session.commit()
    return web.Response(status=204)


@routes.post("/purge")
async def purge(request):
    async with request.app["lock"]:
        return await _purge(request)


async def _purge(request):
    """ Removes routes that aren't present in the database. """
    session = getsession(request)
    addresses = await Addresses.fromdb(session)
    netlink, ros = request.app["netlink"], request.app["ros"]
    netlink.update()
    count = netlink.remove_outdated(keep=addresses)
    ros.update()
    ros_count = ros.remove_outdated(keep=addresses)
    return web.json_response({"removed": count, "removed_ros": ros_count})


