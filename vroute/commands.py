from cleo import Command
import pyroute2

from .db import Host, Address
from .logger import log, debug
from .util import WindowIterator


class AddRecord(Command):
    """
    Adds a new record to the database.

    add
        { hostname* : FQDNs to add. }
        { --resolve : If set, hostnames will be automatically resolved upon save. }
        { --comment= : Comment. }
    """

    def handle(self):
        hostnames = self.argument("hostname")
        # detects malformed arguments in tests
        assert isinstance(hostnames, list), "'--hostnames' value isn't a list."
        session = self._application.new_session()
        for hostname in hostnames:
            debug("Got hostname <info>%s</>", hostname)
            if session.query(Host).filter(Host.name == hostname).first():
                raise ValueError(f"Record {hostname} is already present")
            record = Host()
            record.name = hostname
            record.comment = self.option("comment")
            session.add(record)
            if self.option("resolve"):
                # commit to assign id to the record
                # so foreign key could be created
                session.commit()
                addrs = record.resolve(v6=self._application.vroute.cfg.v6_enabled)
                log("Using addresses <info>%s</> for <info>%s</>", addrs, hostname)
                session.add_all(addrs)
        session.commit()


class RemoveRecord(Command):
    """
    Removes hostname from the database.
    
    remove
        { hostname* : FQDNs to remove }
    """

    def handle(self):
        hostnames = self.argument("hostname")
        session = self._application.new_session()
        for name in hostnames:
            val = session.query(Host).filter(Host.name == name).first()
            if val is None:
                raise ValueError(f"Host {val} does not exist.")
            session.delete(val)
        session.commit()


class ShowRecords(Command):
    """
    Shows saved records.

    show
    """

    def handle(self):
        self.init_colors()
        session = self._application.new_session()
        for host in session.query(Host):
            comment = (" - " + host.comment) if host.comment else ""
            addrs = WindowIterator(
                session.query(Address).filter(Address.host_id == host.id)
            )
            log(f"<info>{host.name}</info>{comment}")
            if addrs.has_any:
                for addr in addrs:
                    symbol = "├──" if not addrs.last else "└──"
                    log(f"    {symbol} <fg=green>{addr.value}</>")
            else:
                log("    └── <fg=cyan>No addresses resolved yet.</>")

    def init_colors(self):
        for color in ["green", "cyan"]:
            self.set_style(color, fg=color)


class SyncRoutes(Command):
    """
    Synchronize internal database with the system routing table.

    sync
        { --routeros : If set, also synchronize with the RouterOS routing table. }
    """

    def handle(self):
        config = self._application.vroute.cfg.get("routeros")
        session = self._application.new_session()
        routeros = config if self.option("routeros") else None
        sync_routes(session, routeros=routeros)


def sync_routes(session, routeros: dict=None):
    pass
