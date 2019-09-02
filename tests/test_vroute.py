from datetime import timedelta, datetime

import pytest
import toml
from vroute import __version__
from vroute.routing import RouteManager, RouterosManager
from vroute.db import Host, Address
from vroute.cfg import Configuration
from vroute.util import WindowIterator

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
    """ Checks adding and resolving new host """
    helpers.mock_rule(rule_exists=True)
    helpers.mock_resolve("1.2.3.4")
    await helpers.post("/", host="example.com")
    assert not RouteManager.get_rules.called
    assert not RouteManager.rule.called
    assert len(list(query(Host))) == 1
    record = query(Host).filter(Host.name == "example.com").first()
    assert record
    assert record.name == "example.com"
    assert datetime.now() < record.expires < datetime.now() + timedelta(seconds=300)
    assert not record.comment
    assert query(Address).first()


@pytest.mark.skip("not implemented")
async def test_add_comments(helpers, query):
    helpers.mock_resolve("1.2.3.4")
    await helpers.post("/", host="example.com", comment="test")
    assert query(Host).first().comment == "test"


async def test_del_hosts(helpers, session, query):
    """ Check that /rm removes only host and doesn't touch Address """
    helpers.add_host("example.com", "1.2.3.4")
    assert query(Address).first()
    await helpers.post("/rm", host="example.com")
    assert not query(Host).first()
    assert not query(Address).first()


# # # # # # # # # #
# 'show' command  #
# # # # # # # # # #


async def test_show_empty(helpers, query):
    response = await helpers.get("/")
    assert response.status == 204


async def test_show(helpers, query):
    helpers.add_host("example.com", "1.2.3.4")
    response = await helpers.get("/")
    assert response.status == 200
    assert await response.json() == {
        "example.com": {"addrs": ["1.2.3.4"], "comment": None}
    }
