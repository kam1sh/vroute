import asyncio
from datetime import timedelta, datetime
import typing as ty
import logging

import aiodns

from .util import with_netmask

log = logging.getLogger(__name__)
    

class Rule:
    def __init__(self, table, priority):
        self.table = table
        self.priority = priority

    @classmethod
    def fromdict(cls, raw: dict):
        attrs = dict(raw["attrs"])
        log.debug("Rule attrs: %s", attrs)
        return cls(table=raw["table"], priority=attrs.get("FRA_PRIORITY"))

    def __repr__(self):
        return f"<Rule({self.table!r})>"


class Route:
    """ Linux (netlink) route. """
    __slots__ = ("dst", "via", "table", "netmask")

    def __init__(self, dst: str, via: int, table: int, netmask: ty.Optional[int] = 32):
        self.dst = dst
        self.via = via
        self.table = table
        self.netmask = netmask

    @classmethod
    def fromdict(cls, raw: dict):
        attrs = dict(raw["attrs"])
        log.debug("Route attrs: %s", attrs)
        netmask = raw["dst_len"]
        via = attrs["RTA_OIF"]
        return cls(dst=attrs["RTA_DST"], via=via, table=raw["table"], netmask=netmask)

    def with_netmask(self):
        return f"{self.dst}/{self.netmask}"

    def __hash__(self):
        return hash(self.with_netmask())


class RosRoute:
    """ RouterOS route. """
    __slots__ = ("id", "dst")

    def __init__(self, id, dst):
        self.id = id
        self.dst = dst

    @classmethod
    def fromdict(cls, raw: dict):
        return cls(raw[".id"], dst=raw["address"])

    def with_netmask(self):
        return with_netmask(self.dst)

    def __hash__(self):
        return hash(self.with_netmask())

class Interface:
    def __init__(self, raw):
        self.num = raw["index"]
        self.state = raw["state"]
        attrs = dict(raw["attrs"])
        self.name = attrs["IFLA_IFNAME"]
