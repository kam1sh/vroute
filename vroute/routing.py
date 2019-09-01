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
        self.current = self.get_routes()

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

    def get_routes(
        self, family=255, match=None, table=None, **kwarg
    ) -> ty.Dict[str, Route]:
        """ Returns dictionary of addresses without prefix in VPN (or other) table. """
        out = super().get_routes(family, match, table=table or self.table, **kwarg)
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
            self.added += 1
        return added, skipped

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

    def get_routes(self) -> ty.Dict[str, RosRoute]:
        resp = self.api.get_resource("/ip/route").get(**{"routing-mark": self.table})
        return {x.without_prefix(): x for x in map(RosRoute.fromdict, resp)}

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
    rules = iproute.get_rules()
    targets = []
    for rule in map(Rule.fromdict, rules):
        if rule.table == table_id:
            targets.append(rule)
    if not targets:
        # create new rule if there is no any
        Rule(table=table_id, priority=priority).create(iproute)
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
