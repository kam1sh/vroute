from vroute import Application
from vroute.db import Database


def pytest_addoption(parser):
    parser.addoption("--db-log", action="store_true", help="Enable database logging")

def pytest_configure(config):
    app = Application()
    app.load_db("sqlite:///:memory:", debug=config.getoption("--db-log"))
