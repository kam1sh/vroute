import cleo
from cleo import Command
from .db import Database
from .cfg import Configuration
from . import __version__

class Application(cleo.Application):
    def run(self):
        cfg = Configuration()
        database = Database()
        database.load("sqlite:///:memory:")
        return super().run()


class AddRecord(Command):
    """
    Adds a new record to the database

    add-record
        {hostname? : FQDN to add}
    """

    def handle(self):
        pass

def main():
    app = Application(name="Network servant", version=__version__)
    app.add(AddRecord())
    app.run()
