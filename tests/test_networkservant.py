from networkservant import __version__
import toml

def test_version():
    with open("pyproject.toml") as fp:
        toml_version = toml.load(fp)["tool"]["poetry"]["version"]
    assert __version__ == toml_version
