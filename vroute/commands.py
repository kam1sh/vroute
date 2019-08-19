from cleo import Command
import pendulum
import pyroute2

from .db import Host, Address
from .logger import log, verbose, debug
from .util import WindowIterator
from . import routing


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
                log(
                    "Using addresses <info>%s</> for <info>%s</>", addrs, hostname
                )
                session.add_all(addrs)
            else:
                log("Record <info>%s</> added.", hostname)
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
        gen = WindowIterator(session.query(Host))
        if not gen.has_any:
            log("Database is empty.")
            return 0
        for host in gen:
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


from pprint import pprint


class SyncRoutes(Command):
    """
    Synchronize internal database with the system routing table.

    sync
        { --routeros : If set, also synchronize with the RouterOS routing table. }
    """

    def session(self):
        return self._application.new_session()

    def handle(self):
        config = self._application.vroute.cfg
        priority = config.get("vpn.rule.priority")
        if priority is None:
            raise ValueError("Please specify rule priority in the configuration file.")
        table = config.get("vpn.table_id")
        if table is None:
            raise ValueError("Please specify table ID in the configuration file.")
        # routeros = config.get("routeros") if self.option("routeros") else None
        session = self._application.new_session()
        query = session.query
        with pyroute2.IPRoute() as ipr:
            try:
                routing.add_rule(priority=priority, table_id=table, iproute=ipr)
            except (routing.MultipleRulesExists, routing.DifferentRuleExists) as e:
                log("<warn>%s</>", e)
            except routing.RuleExistsError as e:
                verbose("%s", e)
            # TODO resolve addresses
            # TODO remove old routes
            # TODO add new routes

    def resolve(self):
        session = self.session()
        for host in session.query(Host):
            resolved = host.resolve_if_needs()
            session.add_all(resolved)
            session.commit()
