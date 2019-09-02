import logging
import typing as ty

from .models import Addresses, Rule, Host, Route, RosRoute, Interface
import pyroute2
import routeros_api


log = logging.getLogger(__name__)


class RouteManager(pyroute2.IPRoute):
    """Manager of Linux routes"""

    def __init__(self, interface: str, table: int, priority: int):
        super().__init__()
        self.interface = find_interface(self, interface)
        self.table = table
        self.priority = priority
        self.current = self.show_routes()

    def show_rules(self) -> ty.Iterable["Rule"]:
        return map(Rule.fromdict, self.get_rules())

    def check_rule(self, priority: int = None):
        priority = priority or self.priority
        if not priority:
            log.error("Failed to add rule - no priority provided")
        try:
            add_rule(priority=priority, table_id=self.table, iproute=self)
        except (MultipleRulesExists, DifferentRuleExists) as e:
            log.warning(e)
        except RuleExistsError as e:
            log.info(e)

    def show_routes(
        self, **kwargs
    ) -> ty.Dict[str, Route]:
        """ Returns dictionary of addresses without prefix in VPN (or other) table. """
        out = self.get_routes(table=self.table, **kwargs)
        return {x.without_prefix(): x for x in map(Route.fromdict, out)}

    def add(self, addr: Route):
        addr = addr.with_prefix()
        self.route("add", dst=addr, oif=self.interface.num, table=self.table)

    def add_all(
        self, addrs: ty.Iterable[Route], to_skip: ty.Collection[Route]
    ) -> ty.Tuple[int, int]:
        """ Adds all routes that are not in the skip list, returns counters of how many added and skipped. """
        added, skipped = 0, 0
        for addr in filter(lambda x: x not in to_skip, addrs):
            if addr in to_skip:
                skipped += 1
                continue
            self.add(addr)
            added += 1
        return added, skipped

    def remove_outdated(self, keep: ty.Collection[str]) -> int:
        current = self.show_routes()
        removed = 0
        for route in current:
            if route in keep:
                continue
            self.route("del", dst=f"{route}/32", oif=self.interface.num, table=self.table)
            removed += 1
        return removed

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


class RouterosManager(routeros_api.RouterOsApiPool):
    def __init__(self, addr, username, password, table, vpn_host, **kwargs):
        super().__init__(addr, username, password, **kwargs)
        self.table = table
        self.api = self.get_api()
        self.vpn_host = vpn_host
        self._route = self.api.get_resource("/ip/route")

    # moved in method for mocking
    def get_raw_routes(self):
        return self._route.get(**{"routing-mark": self.table})

    def get_routes(self) -> ty.Dict[str, RosRoute]:
        resp = self.get_raw_routes()
        return {x.without_prefix(): x for x in map(RosRoute.fromdict, resp)}

    def _add_route(self, params: dict):
        return self._route.add(**params)

    def _rm_route(self, id_):
        return self._route.remove(id=id_)

    def add_routes(self, addresses: ty.Iterable, to_skip: ty.Collection):
        for addr in addresses:
            if addr in to_skip:
                continue
            params = {
                "dst-address": addr.with_prefix(),
                "gateway": self.vpn_host,
                "routing-mark": self.table,
            }
            log.debug("Create route arguments: %s", params)
            resp = self._add_route(params)
            log.debug("ROS response: %s", resp)

    def remove_outdated(self, keep: ty.Collection[str]) -> int:
        current = self.get_routes()
        removed = 0
        for rstr, route in current.items():
            if rstr in keep:
                continue
            self._rm_route(route.id)
            removed += 1
        return removed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, value, tb):
        self.disconnect()

    @classmethod
    def fromconf(cls, cfg: dict):
        if cfg is None:
            raise ValueError("Specify RouterOS connection and routing settings.")
        return cls(
            cfg["addr"],
            username=cfg["username"],
            password=cfg["password"],
            table=cfg["table"],
            vpn_host=cfg["vpn_addr"],
        )


def add_rule(table_id, priority, iproute):
    """ Adds new rule for all addresses with lookup to a specified table. """
    targets = [rule for rule in iproute.show_rules() if rule.table == table_id]
    if not targets:
        # create new rule if there is no any
        iproute.rule(action="add", table=table_id, priority=priority)
    elif len(targets) == 1:
        if targets[0].priority == priority:
            raise RuleExistsError(targets[0])
        else:
            raise DifferentRuleExists(targets[0])
    else:
        raise MultipleRulesExists(targets)


def find_interface(ipr, name):
    interfaces = [x for x in map(Interface, ipr.get_links()) if x.name == name]
    if not interfaces:
        raise ValueError(f"Failed to find interface with name {name!r}.")
    # elif len(interfaces) > 1:
    #     raise ValueError("It can't be!")
    return interfaces[0]


# # # # # # # # # #
# Rule exceptions #
# # # # # # # # # #


class RuleError(ValueError):
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
