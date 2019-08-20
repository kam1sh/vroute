import asyncio
from datetime import timedelta, datetime
import re

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
import aiodns

from .logger import log, verbose, debug

Base = declarative_base()


class Addresses(set):
    """ list with IPv4/v6 addresses """

    def __init__(self):
        super().__init__()
        # by default host.aresolve() will retry
        # to resolve after 10 minutes
        self.ttl = 300

    def remove_outdated(self, current_table: list, ipr):
        """
        Removes outdated address both from the table provided and the routing table,
        and returns what addresses you may skip.
        """
        current = {x.dst: x for x in map(Route.fromdict, current_table)}
        to_skip = set()
        # remove all that's not in the db
        outdated = 0
        for outdated, addr in enumerate(tuple(current.keys())):
            if addr in self:
                # route already added, skipping
                verbose("Route %s is up to date.", addr)
                to_skip.add(addr)
                continue
            verbose("Removing route %s", addr)
            current[addr].remove(ipr)
            del current[addr]
        log(
            "Removed <info>%s</> outdated routes, <info>%s</> are up to date.",
            outdated,
            len(to_skip),
        )
        return to_skip

    def add_routes(self, skip_list, callable):
        for addr in filter(lambda x: x not in skip_list, self):
            # import pdb; pdb.set_trace()
            callable(f"{addr.value}/32")


class IpMixin:
    _v4_pattern = re.compile(r"([\d\.]+)(/32)?")

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

    async def aresolve(self, v6=False, resolver=None) -> list:
        resolver = resolver or self.resolver
        answer = await resolver.query(self.name, "AAAA" if v6 is True else "A")
        out = Addresses()
        # there may be multiple IP addresses per hostname
        for addr in answer:
            record = Address()
            record.v6 = addr.type == "AAAA"
            record.value = addr.host
            record.host_id = self.id
            verbose("%s address: <info>%s</> - ttl", self.name, addr.host)
            out.ttl = min(out.ttl, addr.ttl)
            out.add(record)
        self.expires = datetime.now() + timedelta(seconds=out.ttl)
        return out

    def resolve(self, v6=False):
        loop = asyncio.get_event_loop()
        coro = self.aresolve(v6=v6)
        result = loop.run_until_complete(coro)
        return result

    def addresses(self, session, v6=False):
        """
        Resolve and return new addresses if TTL expired,
        otherwise returns existing addresses.
        """
        addrs = session.query(Address).filter(Address.host_id == self.id)
        if self.expires is None or self.expires < datetime.now():
            addrs.delete()
            addrs = self.resolve(v6=v6)
            session.add_all(addrs)
        return addrs

    def __repr__(self):
        return f"<Host({self.name!r})>"


class Address(Base, IpMixin):
    _v4_pattern = re.compile(r"([\d\.]+)(/32)?")
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    v6 = Column(Boolean, default=False)
    host_id = Column(
        Integer, ForeignKey(Host.id, ondelete="CASCADE"), nullable=False, index=True
    )
    value = Column(String)

    def __str__(self):
        """ Returns address without prefix. """
        if self.v6:
            raise NotImplementedError()
        return self.unprefix(self.value)

    def __eq__(self, value):
        # both have prefix or both doesn't
        if self.value == value:
            return True
        try:
            value = self.unprefix(value)
        except ValueError:
            return False
        return str(self) == value

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
        debug("Rule attrs: %s", attrs)
        return cls(table=raw["table"], priority=attrs.get("FRA_PRIORITY"))

    def create(self, iproute):
        self._action(iproute, action="add")

    def remove(self, iproute):
        self._action(iproute, action="del")

    def _action(self, iproute, action):
        resp = iproute.rule(
            action, src="0.0.0.0/0", table=self.table, priority=self.priority
        )
        if resp:
            debug("Rule %s event response: %s", action, resp[0].get("event"))

    def __repr__(self):
        return f"<Rule({self.table!r})>"


class Route:
    __slots__ = ("dst", "via")

    def __init__(self, dst: str, via: int):
        self.dst = dst
        self.via = via

    @classmethod
    def fromdict(cls, raw: dict):
        attrs = dict(raw["attrs"])
        debug("Route attrs: %s", attrs)
        via = attrs["RTA_OIF"]
        return cls(dst=attrs["RTA_DST"], via=via)

    def remove(self, iproute):
        self._action(iproute, "del")

    def _action(self, iproute, action):
        debug("dst=%s; oif=%s", self.dst, self.via)
        resp = iproute.route(action, dst=self.dst, oif=self.via)
        debug("response: %s", resp)


class Interface:
    def __init__(self, raw):
        self.num = raw["index"]
        self.state = raw["state"]
        attrs = dict(raw["attrs"])
        self.name = attrs["IFLA_IFNAME"]
