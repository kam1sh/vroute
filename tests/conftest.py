from pathlib import Path
import shutil

import pytest
import vroute

config_template = Path(__file__).parent.parent / "config-template.yml"

def pytest_addoption(parser):
    parser.addoption("--db-log", action="store_true", help="Enable database logging")

@pytest.fixture(scope="session", autouse=True)
def app(pytestconfig, tmp_path_factory):
    cfg_path = tmp_path_factory.mktemp("configdir") / "config.yml"
    shutil.copyfile(config_template, cfg_path)
    app = vroute.VRoute()
    app.read_config(file=cfg_path)
    app.load_db("/:memory:", debug=pytestconfig.getoption("--db-log"))
    return app
