from networkservant.db import database


def pytest_addoption(parser):
    parser.addoption("--db-log", action="store_true", help="Enable database logging")

def pytest_configure(config):
    database.load("sqlite:///:memory:", debug=config.getoption("--db-log"))
