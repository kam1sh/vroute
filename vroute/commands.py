from cleo import Command
from .db import AddressRecord


class AddRecord(Command):
    """
    Adds a new record to the database.

    add
        { hostname* : FQDNs to add. }
        { --resolve : If set, hostnames will be automatically resolved upon save. }
        { --comment= : Comment. }
    """

    def handle(self):
        hostname = self.argument("hostname")
        session = self._application.new_session()
        if session.query(AddressRecord).first():
            raise ValueError(f"Record {hostname} is already present")
        record = AddressRecord()
        record.hostname = hostname
        if self.option("resolve"):
            record.resolve()
        record.comment = self.option("comment")
        session.add(record)
        session.commit()
