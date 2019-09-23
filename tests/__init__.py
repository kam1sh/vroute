import asyncio
from copy import deepcopy
from datetime import timedelta, datetime
from json import dumps as jsondump

import click.testing
from vroute.routing import RouteManager, RouterosManager
from vroute.models import Host, Address

from . import samples


class DumbFuture(asyncio.Future):
    def __init__(self, value):
        super().__init__()
        self.set_result(value)


class AnswerStub:
    def __init__(self, host, ttl, kind="A"):
        self.host = host
        self.ttl = ttl
        self.type = kind


class Helpers:
    def __init__(self, mocker, session, requests):
        self.mocker = mocker
        self.session = session
        self.requests = requests

    def add_host(self, name, *addresses, ttl=300):
        host = Host(name=name, expires=datetime.now() + timedelta(seconds=ttl))
        self.session.add(host)
        self.session.commit()
        for address in addresses:
            addr = Address()
            addr.host_id = host.id
            addr.value = address
            self.session.add(addr)
        self.session.commit()

    def mock_resolve(self, *addresses, ttl=300):
        future = asyncio.Future()
        future.set_result([AnswerStub(addr, ttl=ttl) for addr in addresses])
        self.mocker.patch.object(Host.resolver, "query")
        mock = Host.resolver.query
        mock.return_value = future

    def mock_rule(self, exists=True):
        self.mocker.patch.object(RouteManager, "get_rules")
        # priority=40, table=10
        rules = (deepcopy(samples.RULE),) if exists else tuple()
        RouteManager.get_rules.return_value = rules
        self.mocker.patch.object(RouteManager, "rule")

    def mock_interface(self, name="tun0", number=7):
        mock_interface(self.mocker.patch, name=name, number=number)

    def mock_routes(self, *addresses, table=10, oif_num=7, netmask=32):
        mock_netlink(self.mocker.patch)
        routes = []
        for address in addresses:
            route = deepcopy(samples.ROUTE)
            route["attrs"] = [
                ("RTA_TABLE", table),
                ("RTA_DST", address),
                ("RTA_OIF", oif_num),
            ]
            route["dst_len"] = netmask
            routes.append(route)
        RouteManager.get_routes.return_value = routes

    def mock_ros_routes(self, *addresses, list_name="vpn"):
        mock_ros(self.mocker.patch)
        routes = []
        for i, address in enumerate(addresses, start=1):
            route = deepcopy(samples.ROS_ROUTE)
            route["address"] = address + "/32"
            route["list"] = list_name
            route["id"] = f"*{i}"
            routes.append(route)
        RouterosManager.get_raw_routes.return_value = routes

    def get(self, url, params=None):
        return self.requests.get(url, params=params)

    def post(self, url, **json):
        return self.requests.post(url, data=jsondump(json))

    def invoke(self, *args):
        runner = click.testing.CliRunner()
        return runner.invoke(console.cli, args)


def mock_network(patch):
    mock_ros(patch)


def mock_interface(patch, name="tun0", number=7):
    patch.object(RouteManager, "get_links")
    iface = deepcopy(samples.INTERFACE)
    iface["attrs"] = [("IFLA_IFNAME", name)]
    iface["index"] = number
    RouteManager.get_links.return_value = (iface,)

def mock_netlink(patch):
    patch.object(RouteManager, "get_routes")
    patch.object(RouteManager, "route")


def mock_ros(patch):
    patch.object(RouterosManager, "get_api")
    patch.object(RouterosManager, "get_raw_routes")
    patch.object(RouterosManager, "_add_network")
    patch.object(RouterosManager, "_rm_route")
