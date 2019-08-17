from . import CommandTester
import toml
from vroute import __version__

from vroute.db import AddressRecord

def test_version():
    with open("pyproject.toml") as fp:
        toml_version = toml.load(fp)["tool"]["poetry"]["version"]
    assert __version__ == toml_version


def test_db(vrouteobj):
    """ Checks that database schema properly initialized. """
    session = vrouteobj.new_session()
    assert not list(session.query(AddressRecord)) 

def test_addhost(app, vrouteobj):
    cmd = app.find("add")
    tester = CommandTester(cmd)
    tester.run("rutracker.org")
    session = vrouteobj.new_session()
    assert list(session.query(AddressRecord))

