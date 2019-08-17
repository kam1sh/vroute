import logging
from pathlib import Path
import shutil

import pytest
import vroute
from vroute.logger import logger
from vroute import console

config_template = Path(__file__).parent.parent / "config-template.yml"


def pytest_addoption(parser):
    parser.addoption("--db-log", action="store_true", help="Enable database logging")


@pytest.fixture(scope="session", autouse=True)
def vrouteobj(pytestconfig, tmp_path_factory):
    cfg_path = tmp_path_factory.mktemp("configdir") / "config.yml"
    shutil.copyfile(config_template, cfg_path)
    logger.test_log.setLevel(logging.DEBUG)
    vr = vroute.VRoute()
    vr.read_config(file=cfg_path)
    vr.load_db(":memory:", debug=pytestconfig.getoption("--db-log"))
    return vr


@pytest.fixture(scope="session")
def app(vrouteobj):
    app = console.app
    app.vroute = vrouteobj
    return app
