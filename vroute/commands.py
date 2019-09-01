from cleo import Command
import pyroute2
import routeros_api

from .db import Host, Address
from .logger import log, verbose, info
from .util import WindowIterator
from . import routing
from .models import Addresses, RosRoute


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
            # 4. Get current routes, remove outdated and find
            # what routes are up to date
            current = ipr.get_routes(table=table)
            to_skip = addresses.remove_outdated(current, ipr)
            info("table=%s, oif=%s", table, interface.num)
            # 5. Add new routes to the server routing table
            addresses.add_routes(
                to_skip,
                adder=lambda x: ipr.route("add", dst=x, oif=interface.num, table=table),
            )
        if not self.option("routeros"):
            return
        ros = self._application.vroute.cfg.get("routeros")
        if ros is None:
            raise ValueError(
                "To sync with routeros, specify connection and routing settings."
            )
        log("Processing RouterOS table %s", ros["table"])
        conn = routeros_api.RouterOsApiPool(
            ros["addr"], username=ros["username"], password=ros["password"]
        )
        info("Connection established.")
        api = conn.get_api()
        params = {"routing-mark": ros["table"]}
        current = api.get_resource("/ip/route").get(**params)
        info("RouterOS has %s routes.", len(current))
        # current = list(map(RosRoute.fromdict, response))
        to_skip = addresses.remove_outdated(current, api, route_class=RosRoute)
        addresses.add_routes(
            to_skip,
            adder=lambda x: RosRoute(x, via=ros["vpn_addr"], table=ros["table"]).create(
                api
            ),
        )


async def resolve_hosts(session) -> Addresses:
    # set of Address objects
    addresses = Addresses()
    for host in session.query(Host):
        host_addrs = await host.addresses(session)
        for addr in host_addrs:
            addresses.add(addr)
    session.commit()
    return addresses
