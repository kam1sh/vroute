from datetime import timedelta, datetime

import toml
from vroute import __version__, commands
from vroute.db import Host, Address
from vroute.cfg import Configuration
from vroute.logger import logger
from vroute.util import WindowIterator

from . import DumbFuture, AnswerStub


def example_data(session):
    host = Host(name="example.com", expires=datetime.now() + timedelta(seconds=300))
    session.add(host)
    session.commit()
    addr = Address()
    addr.host_id = host.id
    addr.value = "1.2.3.4"
    session.add(addr)
    session.commit()


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


def test_config():
    cfg = Configuration()
    cfg.file = {"key": {"key2": {"key3": "value"}}}
    assert cfg.get("key.key2.key3") == "value"


def test_db(vrouteobj):
    """ Checks that database schema properly initialized. """
    session = vrouteobj.new_session()
    assert not list(session.query(Host))


def test_address():
    assert Address(value="192.168.0.1/32") == "192.168.0.1"
    addr = Address(value="192.168.0.1")
    assert addr == "192.168.0.1/32"
    assert addr == "192.168.0.1"
    assert addr == Address(value="192.168.0.1")
    assert addr == Address(value="192.168.0.1/32")


# # # # # # # # # # # # # # #
# 'add' and 'del' commands  #
# # # # # # # # # # # # # # #


async def test_add_hosts(helpers, query):
    helpers.mock_resolve("1.2.3.4")
    await helpers.post("/", host="example.com")
    assert len(list(query(Host))) == 1
    record = query(Host).filter(Host.name == "example.com").first()
    assert record
    assert record.name == "example.com"
    assert datetime.now() < record.expires < datetime.now() + timedelta(seconds=300)
    assert not record.comment
    assert query(Address).first()


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
    resolved = resolved.pop()
    assert resolved.value == "1.2.3.4"
    assert not resolved.v6
    assert host.expires - datetime.now() < timedelta(301)


def test_resolve_hosts(session, mocker):
    mock_future(mocker, Host.resolver, "query", val=[AnswerStub("1.2.3.4", 300)])
    host = Host(name="example.com", expires=datetime.now())
    session.add(host)
    session.commit()
    commands.resolve_hosts(session)
    assert session.query(Address).first()


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


def test_show_empty(app):
    cmd = app.find("show")
    tester = CommandTester(cmd)
    tester.run()
    expected = "Database is empty.\n"
    assert logger.display_output() == expected


def test_show(session, app):
    example_data(session)
    cmd = app.find("show")
    tester = CommandTester(cmd)
    tester.run()
    expected = """\
example.com
    └── 1.2.3.4
"""
    assert logger.display_output() == expected


def test_show_unresolved(session, app):
    host = Host(name="example.com", expires=datetime.now())
    session.add(host)
    session.commit()

    cmd = app.find("show")
    tester = CommandTester(cmd)
    tester.run()
    expected = """\
example.com
    └── No addresses resolved yet.
"""
    assert logger.display_output() == expected
