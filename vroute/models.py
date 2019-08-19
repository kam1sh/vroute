import asyncio
from datetime import timedelta

from pendulum import now
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
import aiodns

from .logger import verbose, debug

Base = declarative_base()


class Addresses(list):
    """ list with IPv4/v6 addresses """

    def __init__(self):
        super().__init__()
        self.ttl = 604_800  # default ttl = 1 week


class Host(Base):
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
            out.append(record)
        if out:
            self.expires = now() + timedelta(seconds=out.ttl)
        return out

    def resolve(self, v6=False):
        loop = asyncio.get_event_loop()
        coro = self.aresolve(v6=v6)
        result = loop.run_until_complete(coro)
        return result

    def resolve_if_needs(self, v6=False):
        if self.expires is None or self.expires < now():
            return []
        return resolve(v6=v6)

    def __repr__(self):
        return f"<Host({self.name!r})>"


class Address(Base):
    __tablename__ = "addresses"
    id = Column(Integer, primary_key=True)
    v6 = Column(Boolean, default=False)
    host_id = Column(
        Integer, ForeignKey(Host.id, ondelete="CASCADE"), nullable=False, index=True
    )
    value = Column(String)

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
        return cls(table=raw["table"], priority=attrs["FRA_PRIORITY"])

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
