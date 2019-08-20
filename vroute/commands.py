from cleo import Command
import pyroute2

from .db import Host, Address
from .logger import log, verbose, debug
from .util import WindowIterator
from . import routing
from .models import Addresses


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


class SyncRoutes(Command):
    """
    Synchronize internal database with the system routing table.

    sync
        { --routeros : If set, also synchronize with the RouterOS routing table. }
    """

    def session(self):
        return self._application.new_session()

    def _configure(self):
        config = self._application.vroute.cfg
        priority = config.get("vpn.rule.priority")
        if priority is None:
            raise ValueError("Please specify rule priority in the configuration file.")
        table = config.get("vpn.table_id")
        if table is None:
            raise ValueError("Please specify table ID in the configuration file.")
        interface = config.get("vpn.route_to.interface")
        if not interface:
            raise ValueError("Please specify interface in the configuration file.")
        # routeros = config.get("routeros") if self.option("routeros") else None
        return table, priority, interface

    def handle(self):
        table, priority, interface = self._configure()
        session = self._application.new_session()
        # 1. Fetch all hosts and their IP addresses
        addresses = resolve_hosts(session)
        with pyroute2.IPRoute() as ipr:
            # 2. Find interface with its ID by name.
            interface = routing.find_interface(ipr, name=interface)
            # 3. Check rule and add if it doesn't exist
            try:
                routing.add_rule(priority=priority, table_id=table, iproute=ipr)
            except (routing.MultipleRulesExists, routing.DifferentRuleExists) as e:
                log("<warn>%s</>", e)
            except routing.RuleExistsError as e:
                verbose("%s", e)
            addresses = resolve_hosts(session)
            current = ipr.get_routes(table=table)
            to_skip = addresses.remove_outdated(current, ipr)
            addresses.add_routes(
                to_skip,
                callable=lambda x: ipr.route(
                    "add", dst=x, oif=interface.num, table=table
                ),
            )
            # routing.add_routes(addresses, table, interface.num, ipr)
            # TODO add new routes
            # TODO sync with mikrotik


def resolve_hosts(session) -> Addresses:
    # set of Address objects
    addresses = Addresses()
    for host in session.query(Host):
        host_addrs = host.addresses(session)
        for addr in host_addrs:
            addresses.add(addr)
    session.commit()
    return addresses
