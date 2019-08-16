import cleo
from cleo import Command
from .db import Database
from .cfg import Configuration
from . import Application



class AddRecord(Command):
    """
    Adds a new record to the database

    add-record
        {hostname? : FQDN to add}
    """

    def handle(self):
        pass

def main():
    app = Application()
    app.add(AddRecord())
    app.run()
