from datetime import timedelta

import toml
from vroute import __version__
from vroute.db import Host, Address
from vroute.logger import logger
from vroute.util import WindowIterator
import pendulum

from . import CommandTester, DumbFuture, AnswerStub


def example_data(session):
    host = Host()
    host.name = "example.com"
    host.expires = pendulum.now().add(seconds=300)
    session.add(host)
    session.commit()
    addr = Address()
    addr.host_id = host.id
    addr.value = "1.2.3.4"
    session.add(addr)
    session.commit()


def mock_future(mocker, obj, key, val):
    mocker.patch.object(obj, key)
    mock = getattr(obj, key)
    mock.return_value = DumbFuture(val)

# # # # # # #
# utilities #
# # # # # # #

def test_window():
    lst = [1, 2, 3, 4]
    gen = WindowIterator(lst)
    for x in gen:
        if x == 1:
            assert gen.first
        else:
            assert not gen.first
        if x in {2, 3}:
            assert gen.has_any
            assert not gen.first and not gen.last
        if x == 4:
            assert not gen.first and gen.last
    assert list(WindowIterator([1]))
    gen = WindowIterator([1])
    for _ in gen:
        assert gen.last

def test_version():
    with open("pyproject.toml") as fp:
        toml_version = toml.load(fp)["tool"]["poetry"]["version"]
    assert __version__ == toml_version


def test_db(vrouteobj):
    """ Checks that database schema properly initialized. """
    session = vrouteobj.new_session()
    assert not list(session.query(Host))

# # # # # # # # # # # # # # #
# 'add' and 'del' commands  #
# # # # # # # # # # # # # # #

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

def test_del_hosts(app, session):
    example_data(session)
    cmd = app.find("remove")
    tester = CommandTester(cmd)
    tester.run(("hostname", ["example.com"]))
    assert not session.query(Host).first()

# # # # # # # # # #
# 'show' command  #
# # # # # # # # # #

def test_show(session, app):
    example_data(session)
    cmd = app.find("show")
    tester = CommandTester(cmd)
    tester.run()
    assert logger

    expected = """\
example.com
    └── 1.2.3.4
"""
    assert logger.display_output() == expected

def test_show_resolved(session, app):
    pass

# # # # # # # # # #
# 'sync' command  #
# # # # # # # # # #

def test_add_table(mocker, session):
    example_data(session)

