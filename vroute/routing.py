from abc import ABC, abstractmethod
import logging
import typing as ty

import pyroute2
import routeros_api
import routeros_api.resource

from .models import Rule, Route, RosRoute, Interface
from .util import with_netmask

log = logging.getLogger(__name__)


class Manager(ABC):
    name = "manager"

    @classmethod
    @abstractmethod
    def fromconf(cls, cfg: dict) -> "Manager": ...

    @abstractmethod
    def add(self, network: str):
        """ Add new network. """

    def prepare(self):
        pass

    def disconnect(self):
        pass

    @abstractmethod
    def current(self) -> ty.List[Route]:
        """ List current networks. """

    # def sync(self, routes: Addresses) -> dict:
    #     """ Performs synchronization. """
    #     self.update()
    #     t = time()
    #     to_skip = routes.what_exists(self.current)
    #     log.info("Found %s routes to skip in %.2f seconds.", len(to_skip), time() - t)
    #     t = time()
    #     added, skipped = self.do_sync(routes, to_skip)
    #     log.info("Performed synchronization in %.2f seconds.", time() - t)
    #     return dict(added=added, skipped=skipped)


class LinuxRouteManager(pyroute2.IPRoute, Manager):
    """Manager of Linux routes"""
    name = "linux"

    def __init__(self, interface: str, table: int, priority: int):
        super().__init__()
        self._interface = interface
        self.table = table
        self.priority = priority
        self.interface: Interface = self.find_interface()
        self.prepare()

    @classmethod
    def fromconf(cls, cfg: dict):
        priority = cfg.get("vpn.rule.priority")
        if priority is None:
            raise ValueError("Please specify rule priority in the configuration file.")
        table = cfg.get("vpn.table_id")
        if table is None:
            raise ValueError("Please specify table ID in the configuration file.")
        interface = cfg.get("vpn.route_to.interface")
        if not interface:
            raise ValueError("Please specify interface in the configuration file.")
        return cls(interface=interface, table=table, priority=priority)

    def prepare(self):
        self.check_rule()
        self.interface = self.find_interface()

    def add(self, network: str):
        try:
            self.route(
                "add", dst=network, oif=self.interface.num, table=self.table, scope="link")
        except pyroute2.netlink.exceptions.NetlinkError as err:
            if err.code != 17: # 17 = route exists
                raise

    def current(self):
        return map(Route.fromdict, self.get_routes(table=self.table))

    ### rules ###
    def show_rules(self) -> ty.Iterable:
        return map(Rule.fromdict, self.get_rules(table=self.table))

    def check_rule(self, priority: int = None):
        priority = priority or self.priority
        if not priority:
            log.error("Failed to add rule - no priority provided")
        try:
            self.add_rule()
        except (MultipleRulesExists, DifferentRuleExists) as e:
            log.warning(e)
        except RuleExistsError as e:
            log.info(e)

    def add_rule(self):
        """ Adds new rule for all addresses with lookup to a specified table. """
        targets = [rule for rule in self.show_rules() if rule.table == self.table]
        if not targets:
            # create new rule if there is no any
            self.rule("add", table=self.table, priority=self.priority)
        elif len(targets) == 1:
            if targets[0].priority == self.priority:
                raise RuleExistsError(targets[0])
            else:
                raise DifferentRuleExists(targets[0])
        else:
            raise MultipleRulesExists(targets)

    ### interface ###
    def find_interface(self, name=None):
        name = name or self._interface
        interfaces = [x for x in map(Interface, self.get_links()) if x.name == name]
        if not interfaces:
            raise ValueError(f"Failed to find interface with name {name!r}.")
        # elif len(interfaces) > 1:
        #     raise ValueError("It can't be!")
        return interfaces[0]


class RouterosManager(routeros_api.RouterOsApiPool, Manager):
    name = "routeros"

    def __init__(self, addr, username, password, list_name, **kwargs):
        super().__init__(addr, username, password, **kwargs)
        self.list_name = list_name
        self.api: ty.Optional[routeros_api.api.RouterOsApi] = None
        self.cmd: ty.Optional[routeros_api.resource.RouterOsResource] = None
        self.prepare()

    @classmethod
    def fromconf(cls, cfg: dict):
        if cfg is None:
            raise ValueError("Specify RouterOS connection and routing settings.")
        return cls(
            cfg["addr"],
            username=cfg["username"],
            password=cfg["password"],
            list_name=cfg["list_name"],
        )

    def add(self, network: str):
        params = {"address": network, "list": self.list_name}
        self._add_network(params)

    def current(self) -> ty.List:
        resp = self.get_raw_routes()
        return map(RosRoute.fromdict, resp)

    def prepare(self):
        self.api = self.get_api()
        self.cmd = self.api.get_resource("/ip/firewall/address-list")

    def do_sync(self, routes, to_skip):
        return self.add_all(routes, to_skip)

    # moved in method for mocking
    def get_raw_routes(self):
        return self.cmd.get(**{"list": self.list_name})

    def _add_network(self, params: dict):
        return self.cmd.add(**params)

    def _rm_route(self, id_):
        return self.cmd.remove(id=id_)

    def add_all(self, addresses: ty.Iterable[str], to_skip: ty.Collection):
        added, skipped = 0, 0
        for addr in addresses:
            if addr in to_skip:
                skipped += 1
                continue
            added += 1
            params = {"address": with_netmask(addr), "list": self.list_name}
            log.debug("Add network arguments: %s", params)
            resp = self._add_network(params)
            log.debug("ROS response: %s", resp)
        return added, skipped

    def remove_outdated(self, keep: ty.Collection[str]) -> int:
        removed = 0
        for route in self.current:
            rstr = route.with_netmask()
            if rstr in keep:
                continue
            self._rm_route(route.id)
            removed += 1
        return removed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, value, tb):
        self.disconnect()

# # # # # # # # # #
# Rule exceptions #
# # # # # # # # # #


class RuleError(RuntimeError):
    """ Base exception for rule errors. """

    def __init__(self, obj):
        self.obj = obj
        super().__init__(self.format())

    def format(self):
        return ""


class RuleExistsError(RuleError):
    def format(self):
        return "Rule already exists, skipping."


class DifferentRuleExists(RuleExistsError):
    def format(self):
        return f"Rule already exists with priority {self.obj.priority}."


class MultipleRulesExists(RuleExistsError):
    def format(self):
        return (
            "There's more than one rule for the target table."
            " I have a bad feeling about this."
        )
