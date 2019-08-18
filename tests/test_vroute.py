from datetime import timedelta

import toml
from vroute import __version__
from vroute.db import Host, Address
import pendulum

from . import CommandTester, DumbFuture, AnswerStub


def mock_future(mocker, obj, key, val):
    mocker.patch.object(obj, key)
    mock = getattr(obj, key)
    mock.return_value = DumbFuture(val)


def test_version():
    with open("pyproject.toml") as fp:
        toml_version = toml.load(fp)["tool"]["poetry"]["version"]
    assert __version__ == toml_version


def test_db(vrouteobj):
    """ Checks that database schema properly initialized. """
    session = vrouteobj.new_session()
    assert not list(session.query(Host))

# # # # # # # # #
# 'add' command #
# # # # # # # # #

def test_add_hosts(app, query):
    cmd = app.find("add")
    tester = CommandTester(cmd)
    tester.run(("hostname", ["example.com", "example.org"]))
    assert len(list(query(Host))) == 2
    record = query(Host).filter(Host.name == "example.com").first()
    assert record
    assert record.name == "example.com"
    assert not record.expires
    assert not record.comment
    assert query(Address).first() is None


def test_add_comments(app, query):
    cmd = app.find("add")
    tester = CommandTester(cmd)
    tester.run(("hostname", ["example.com"]), ("--comment", "test"))
    assert query(Host).first().comment == "test"


def test_resolve_host(mocker):
    mock_future(mocker, Host.resolver, "query", val=[AnswerStub("1.2.3.4", 300)])
    host = Host(name="example.com")
    resolved = host.resolve()
    assert len(resolved) == 1
    resolved = resolved[0]
    assert resolved.value == "1.2.3.4"
    assert not resolved.v6
    assert host.expires - pendulum.now() < timedelta(301)


def test_add_resolve(mocker, app, query):
    mock_future(mocker, Host.resolver, "query", val=[AnswerStub("1.2.3.4", 300)])
    cmd = app.find("add")
    tester = CommandTester(cmd)
    tester.run(("hostname", ["example.com"]), ("--resolve", True))
    assert query(Address).first()

# # # # # # # # # #
# 'sync' command  #
# # # # # # # # # #

def test_add_table(mocker, session):
    host = Host()
    host.name = "example.com"
    host.expires = pendulum.now().add(seconds=300)
    session.add(host)
    session.commit()
    addr = Address()
    addr.host_id = host.id
    addr.value = "1.2.3.4"
    session.add(host)
    session.commit()
