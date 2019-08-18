from copy import deepcopy
from pathlib import Path
import shutil
import logging

import pytest
from vroute.logger import logger
from vroute import console, VRoute, db, cfg

config_template = Path(__file__).parent.parent / "config-template.yml"


def pytest_addoption(parser):
    parser.addoption("--log-sql", action="store_true", help="Enable SQL logging")

CONFIG = dict(
    vpn=dict(
        rule={"name": "vpn", "priority": 40},
        route_to={"interface": "tun0"},
    ),
    routeros=dict(
        addr="127.0.0.1",
        vpn_addr="127.0.0.2",
        username="admin",
        password=""
    )
)

@pytest.fixture(scope="session")
def config():
    config = cfg.Configuration()
    config.file = deepcopy(CONFIG)
    return config

@pytest.fixture(autouse=True)
def reload_config(config):
    config.file = deepcopy(CONFIG)

@pytest.fixture(scope="session", autouse=True)
def vrouteobj(pytestconfig, config):
    logger.set_verbosity(logger.VERBOSITY_DEBUG)
    vrobj = VRoute()
    vrobj.cfg = config
    if pytestconfig.getoption("--log-sql"):
        sql_log = logging.getLogger("sqlalchemy")
        sql_log.setLevel(logging.INFO)
    vrobj.load_db(":memory:")
    return vrobj


@pytest.fixture(autouse=True)
def wipe_database(vrouteobj):
    logger.enable_storage()
    engine = vrouteobj.db.engine
    db.Base.metadata.drop_all(bind=engine)
    db.Base.metadata.create_all(bind=engine)

@pytest.fixture(scope="session")
def app(vrouteobj):
    app = console.Application()
    app.vroute = vrouteobj
    return app


@pytest.fixture
def session(app):
    return app.new_session()

@pytest.fixture
def query(session):
    return session.query
