import asyncio
from datetime import timedelta, datetime
import typing as ty
import logging

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
import aiodns

from .util import with_netmask

Base = declarative_base()
log = logging.getLogger(__name__)


class Network:
    def with_netmask(self):
        """
        :return: string in format <network>/<subnet_suffix>
        """
        raise NotImplementedError


class Addresses(set):
    """ Smart collection for IPv4/v6 addresses/networks. """

    def __init__(self, ignorelist=None):
        super().__init__()
        # by default host.aresolve() will retry
        # to resolve after 10 minutes
        self.ttl = 300
        self.ignore = ignorelist or []

    @classmethod
    async def fromdb(cls, session, ignorelist=None):
        """ Returns all addresses from database. """
        addresses = cls(ignorelist=ignorelist)
        for host in session.query(Host):
            try:
                host_addrs = await host.resolve_addresses(session)
            except aiodns.error.DNSError:
                log.error("Error resolving %s", host)
                continue
            for addr in host_addrs:
                addresses.add(with_netmask(addr))
        session.commit()
        for addr in session.query(Address).filter(Address.host_id.is_(None)):
            addresses.add(addr)
        return addresses

    def what_exists(self, current_table: ty.Iterable["Route"]) -> ty.Collection[str]:
        """ Returns collection of addresses that already exists in current table """
        to_skip = set()
        for route in current_table:
            address = route.with_netmask()
            if address in self:
                to_skip.add(address)
        for item in self.ignore:
            to_skip.add(with_netmask(item))
        return to_skip

    def __contains__(self, item):
        return super().__contains__(with_netmask(item))


class Host(Base):  # type: ignore
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
            log.debug("%s address: %s, ttl=%ss", self.name, addr.host, addr.ttl)
            out.ttl = min(out.ttl, addr.ttl)
            out.add(record)
        self.expires = datetime.now() + timedelta(seconds=out.ttl)
        return out

    def get_addresses(self, session) -> ty.Collection["Address"]:
        return session.query(Address).filter(Address.host_id == self.id)

    async def resolve_addresses(self, session, v6=False):
        """
        Resolve and return new addresses if TTL expired,
        otherwise returns existing addresses.
        """
        addrs = self.get_addresses(session)
        if self.expires is None or self.expires < datetime.now():
            addrs.delete()
            addrs = await self.aresolve(v6=v6)
            session.add_all(addrs)
        return addrs

    def __repr__(self):
        return f"<Host({self.name!r})>"


class Address(Base, Network):  # type: ignore
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    value = Column(String, index=True)
    v6 = Column(Boolean, default=False)
    host_id = Column(Integer, ForeignKey(Host.id, ondelete="CASCADE"), index=True)

    def with_netmask(self):
        return with_netmask(self.value)

    def __str__(self):
        """ Returns address without prefix. """
        if self.v6:
            raise NotImplementedError()
        return self.with_netmask()

    def __eq__(self, value):
        # both have prefix or both doesn't
        if self.value == value:
            return True
        if self.with_netmask() == value:
            return True
        if self.with_netmask() == with_netmask(value):
            return True
        return False

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return f"<Address({self.value!r})>"


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


class Route(Network):
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


class RosRoute(Network):
    """ RouterOS route. """
    __slots__ = ("dst", "id")

    def __init__(self, dst, id_=None):
        self.dst = dst
        self.id = id_

    @classmethod
    def fromdict(cls, raw: dict):
        return cls(dst=raw["address"], id_=raw["id"])

    def with_netmask(self):
        return with_netmask(self.dst)


class Interface:
    def __init__(self, raw):
        self.num = raw["index"]
        self.state = raw["state"]
        attrs = dict(raw["attrs"])
        self.name = attrs["IFLA_IFNAME"]
