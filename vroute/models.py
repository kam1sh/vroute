import logging
import asyncio
from datetime import timedelta, datetime
import re

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
import aiodns

Base = declarative_base()
log = logging.getLogger(__name__)


class Addresses(set):
    """ list with resolved IPv4/v6 addresses """

    def __init__(self):
        super().__init__()
        # by default host.aresolve() will retry
        # to resolve after 10 minutes
        self.ttl = 300

    def _get_current(self, table: list, clazz=None) -> dict:
        """  """
        route_class = clazz or Route
        return {x.without_prefix(): x for x in map(route_class.fromdict, table)}

    def what_to_skip(self, current_table: dict) -> set:
        to_skip = set()
        for addr in tuple(current_table.keys()):
            if addr in self:
                to_skip.add(addr)
        return to_skip

    def remove_outdated(self, current_table: list, conn, route_class=None):
        """
        Removes outdated address both from the table provided and the routing table,
        """
        current = self._get_current(current_table, route_class)
        # remove all that's not in the db
        for addr in tuple(current.keys()):
            if addr in self:
                continue
            log.info("Removing route %s", addr)
            current[addr].remove(conn)
            del current[addr]

    def add_routeros_routes(self, api, ros_cfg: dict, to_skip=None):
        self.add_routes(
            to_skip or [],
            adder=lambda x: RosRoute(
                x, via=ros_cfg["vpn_addr"], table=ros_cfg["table"]
            ).create(api),
        )

    def add_routes(self, skip_list, adder):
        added = 0
        for addr in filter(lambda x: x not in skip_list, self):
            addr = addr.with_prefix()
            log.info("Appending address %r", addr)
            adder(addr)
            added += 1
        log.info("Added %s routes.", added)


class IpMixin:
    _v4_pattern = re.compile(r"([\d.]+)(/\d+)?")

    def _with_prefix(self, value):
        if not value.endswith("/32"):
            return f"{value}/32"
        return value

    def unprefix(self, addr):
        match = self._v4_pattern.match(addr)
        if not match:
            raise ValueError("Failed to parse address %s" % addr)
        return match.group(1)


class Host(Base):
    # TODO ipv6 support
    __tablename__ = "hosts"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    expires = Column(DateTime, index=True)
    comment = Column(String)

    resolver = aiodns.DNSResolver(loop=asyncio.get_event_loop())

    async def aresolve(self, v6=False, resolver=None) -> set:
        resolver = resolver or self.resolver
        answer = await resolver.query(self.name, "AAAA" if v6 else "A")
        out = Addresses()
        # there may be multiple IP addresses per hostname
        for addr in answer:
            record = Address()
            record.v6 = addr.type == "AAAA"
            record.value = addr.host
            record.host_id = self.id
            log.debug(
                "%s address: <info>%s</>, ttl=<info>%ss</>",
                self.name,
                addr.host,
                addr.ttl,
            )
            out.ttl = min(out.ttl, addr.ttl)
            out.add(record)
        self.expires = datetime.now() + timedelta(seconds=out.ttl)
        return out

    def resolve(self, v6=False):
        loop = asyncio.get_event_loop()
        coro = self.aresolve(v6=v6)
        result = loop.run_until_complete(coro)
        return result

    async def addresses(self, session, v6=False):
        """
        Resolve and return new addresses if TTL expired,
        otherwise returns existing addresses.
        """
        addrs = session.query(Address).filter(Address.host_id == self.id)
        if self.expires is None or self.expires < datetime.now():
            addrs.delete()
            addrs = await self.aresolve(v6=v6)
            session.add_all(addrs)
        return addrs

    def __repr__(self):
        return f"<Host({self.name!r})>"


class Address(Base, IpMixin):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    v6 = Column(Boolean, default=False)
    host_id = Column(
        Integer, ForeignKey(Host.id, ondelete="CASCADE"), nullable=False, index=True
    )
    value = Column(String)

    def with_prefix(self):
        return self._with_prefix(self.value)

    def __str__(self):
        """ Returns address without prefix. """
        if self.v6:
            raise NotImplementedError()
        return self.with_prefix()

    def __eq__(self, value):
        # both have prefix or both doesn't
        if self.value == value:
            return True
        if self.with_prefix().endswith("/32") and self.unprefix(self.value) == value:
            return True
        if self.with_prefix() == value:
            return True
        try:
            value = value.with_prefix()
        except:
            return False

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return f"<Address({self.value!r}>"


class Rule:
    def __init__(self, table, priority):
        self.table = table
        self.priority = priority

    @classmethod
    def fromdict(cls, raw: dict):
        attrs = dict(raw["attrs"])
        log.debug("Rule attrs: %s", attrs)
        return cls(table=raw["table"], priority=attrs.get("FRA_PRIORITY"))

    def create(self, iproute):
        self._action(iproute, action="add")

    def _action(self, iproute, action):
        resp = iproute.rule(
            action, src="0.0.0.0/0", table=self.table, priority=self.priority
        )
        if resp:
            log.debug("Rule %s event response: %s", action, resp[0].get("event"))

    def __repr__(self):
        return f"<Rule({self.table!r})>"


class Route(IpMixin):
    __slots__ = ("dst", "via", "table")

    def __init__(self, dst: str, via: int, table: int):
        self.dst = dst
        self.via = via
        self.table = table

    @classmethod
    def fromdict(cls, raw: dict):
        attrs = dict(raw["attrs"])
        log.debug("Route attrs: %s", attrs)
        via = attrs["RTA_OIF"]
        return cls(dst=attrs["RTA_DST"], via=via, table=raw["table"])

    def remove(self, iproute):
        self._action(iproute, "del")

    def _action(self, iproute, action):
        dst = self.with_prefix()
        log.debug("dst=%s; oif=%s", dst, self.via)
        resp = iproute.route(action, dst=dst, oif=self.via, table=self.table)
        log.debug("response: %s", resp)

    def with_prefix(self):
        if not self.dst.endswith("/32"):
            return f"{self.dst}/32"
        return self.dst

    def without_prefix(self):
        return self.unprefix(self.dst)


class RosRoute(Route):
    __slots__ = ("dst", "via", "table", "id")

    def __init__(self, dst, via, table, id_=None):
        super().__init__(dst, via, table)
        self.id = id_

    @classmethod
    def fromdict(cls, raw: dict):
        return cls(
            dst=raw["dst-address"],
            via=raw["gateway"],
            table=raw["routing-mark"],
            id_=raw["id"],
        )

    def remove(self, api):
        resp = api.get_resource("/ip/route").remove(id=self.id)
        log.debug("ROS response: %s", resp)

    def create(self, api):
        params = {
            "dst-address": self.with_prefix(),
            "gateway": self.via,
            "routing-mark": self.table,
        }
        log.debug("Create route arguments: %s", params)
        resp = api.get_resource("/ip/route").add(**params)
        log.debug("ROS response: %s", resp)


class Interface:
    def __init__(self, raw):
        self.num = raw["index"]
        self.state = raw["state"]
        attrs = dict(raw["attrs"])
        self.name = attrs["IFLA_IFNAME"]
