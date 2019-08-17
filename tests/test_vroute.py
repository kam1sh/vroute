from cleo import CommandTester
import toml
from vroute import __version__


def test_version():
    with open("pyproject.toml") as fp:
        toml_version = toml.load(fp)["tool"]["poetry"]["version"]
    assert __version__ == toml_version


def test_addhost(app):
    cmd = app.find("add")
    tester = CommandTester(cmd)
    tester.set_inputs(["rutracker.org"])
    tester.execute([("command", cmd.get_name())])
