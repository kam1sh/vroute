from copy import deepcopy
from pathlib import Path
import logging

import pytest
from vroute import web
from vroute import console, VRoute, db, cfg

from . import Helpers

config_template = Path(__file__).parent.parent / "config-template.yml"


def pytest_addoption(parser):
    parser.addoption("--log-sql", action="store_true", help="Enable SQL logging")


CONFIG = dict(
    vpn=dict(rule={"name": "vpn", "priority": 40}, route_to={"interface": "tun0"}),
    routeros=dict(
        addr="127.0.0.1", vpn_addr="127.0.0.2", username="admin", password=""
    ),
)


@pytest.fixture()
def config():
    config = cfg.Configuration()
    config.file = deepcopy(CONFIG)
    return config


@pytest.fixture(autouse=True)
def vrouteobj(pytestconfig, config):
    vrobj = VRoute()
    vrobj.cfg = config
    if pytestconfig.getoption("--log-sql"):
        sql_log = logging.getLogger("sqlalchemy")
        sql_log.setLevel(logging.INFO)
    vrobj.load_db(":memory:")
    console.get_vroute = lambda: vrobj
    return vrobj


@pytest.fixture(autouse=True)
def wipe_database(vrouteobj):
    engine = vrouteobj.db.engine
    db.Base.metadata.drop_all(bind=engine)
    db.Base.metadata.create_all(bind=engine)


@pytest.fixture
def session(vrouteobj):
    return vrouteobj.db.new_session()


@pytest.fixture
def helpers(mocker, vrouteobj, session, loop, aiohttp_client):
    webapp = web.get_webapp(app=vrouteobj)
    return Helpers(
        mocker,
        session=session,
        requests=loop.run_until_complete(aiohttp_client(webapp)),
    )


@pytest.fixture
def cli(loop, aiohttp_client):
    app = web.get_webapp(loop)
    return loop.run_until_complete(aiohttp_client(app))


@pytest.fixture
def query(session):
    return session.query
