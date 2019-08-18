from cleo import Command
from .db import Host
from .logger import log, debug

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
