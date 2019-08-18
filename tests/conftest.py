from pathlib import Path
import shutil
import logging

import pytest
from vroute.logger import logger
from vroute import console, VRoute, db

config_template = Path(__file__).parent.parent / "config-template.yml"


def pytest_addoption(parser):
    parser.addoption("--log-sql", action="store_true", help="Enable SQL logging")


@pytest.fixture(scope="session", autouse=True)
def vrouteobj(pytestconfig, tmp_path_factory):
    cfg_path = tmp_path_factory.mktemp("configdir") / "config.yml"
    shutil.copyfile(config_template, cfg_path)
    logger.set_verbosity(logger.VERBOSITY_DEBUG)
    vrobj = VRoute()
    vrobj.read_config(file=cfg_path)
    if pytestconfig.getoption("--log-sql"):
        sql_log = logging.getLogger("sqlalchemy")
        sql_log.setLevel(logging.INFO)
    vrobj.load_db(":memory:")
    return vrobj


@pytest.fixture(scope="session")
def app(vrouteobj):
    app = console.Application()
    app.vroute = vrouteobj
    return app


@pytest.fixture
def session(app):
    return app.new_session()
