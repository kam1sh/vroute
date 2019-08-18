import toml
from vroute import __version__
from vroute.db import AddressRecord

from . import CommandTester


def test_version():
    with open("pyproject.toml") as fp:
        toml_version = toml.load(fp)["tool"]["poetry"]["version"]
    assert __version__ == toml_version


def test_db(vrouteobj):
    """ Checks that database schema properly initialized. """
    session = vrouteobj.new_session()
    assert not list(session.query(AddressRecord))


def test_addhost(app, session):
    cmd = app.find("add")
    tester = CommandTester(cmd)
    tester.run("hostname rutracker.org")
    record = session.query(AddressRecord).first()
    assert record and record.hostname == "rutracker.org"
    assert not record.addrv4
    assert not record.expires
    assert not record.comment
