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

    def get_appdir(self) -> Path:
        """ Returns path to the default application directory. """
        folder = Path.home() / ".local/share/vroute"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @property
    def db_file(self) -> str:
        url = self.get("db.url")
        if not url:
            folder = self.get_appdir()
            url = str(folder.joinpath("db.sqlite3").absolute())
        return url

    @property
    def db_debug(self) -> bool:
        return bool(self.get("db.debug"))

    @property
    def lock_file(self) -> Path:
        file = self.get("lock_file")
        return Path(file) if file else self.get_appdir().joinpath("lock")

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
