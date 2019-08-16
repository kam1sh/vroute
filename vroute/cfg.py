"""
Configuration code: config file loading, environment variables, etc
"""

from pathlib import Path

from yaml import load
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

class Configuration:
    def __init__(self, from_file=None):
        from_file = Path(from_file) if from_file else Path.home() / ".config/vroute.yml"
        if not from_file.exists():
            raise ValueError(
                f"No configuration file found in {from_file}.\n"
                "Please create one according the config-template.yml"
                " in the repository root."
                )
        with from_file.open() as fd:
            self.file = load(fd, Loader=Loader)

    @property
    def db_url(self):
        url = self.get("db.url")
        if not url:
            folder = Path.home() / ".local/share/vroute"
            folder.mkdir(parents=True, exist_ok=True)
            url = str(folder.joinpath("db.sqlite3").absolute())
        return "sqlite://" + url

    @property
    def db_debug(self):
        return self.get("db.debug") or False


    def get(self, pth):
        """
        Returns value by combined key or None.

        >>> config.file["test"]["key"] = 1
        >>> config.get("test.key")
        1
        >>> config.get("test.not.exist")
        None
        """
        keys = pth.split(".")
        if not keys:
            return None
        val = self.file.get(keys.pop(0))
        for key in pth.split("."):
            if not hasattr(val, "get"):
                return None
            val = val.get(key)
        return val
