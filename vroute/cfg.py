"""
Configuration code: config file loading, environment variables, etc
"""

from pathlib import Path

from yaml import load

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader  # type: ignore


class Configuration:
    def __init__(self, from_file=None):
        self.file = None
        if from_file is not None:
            self.from_file(from_file)

    def from_file(self, file):
        from_file = Path(file)
        if not from_file.exists():
            raise ValueError(
                f"No configuration file found in {from_file}.\n"
                "You may create one according the config-template.yml"
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
        url = self.get("db.file")
        if not url:
            folder = self.get_appdir()
            url = str(folder.joinpath("db.sqlite3").absolute())
        return url

    @property
    def db_debug(self) -> bool:
        return bool(self.get("db.debug"))

    @property
    def v6_enabled(self) -> bool:
        return bool(self.get("ipv6"))

    @property
    def listen_port(self):
        return self.get("listen_port") or "1015"

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
        for key in keys:
            if not hasattr(val, "get"):
                return None
            val = val.get(key)
        return val

    def __getitem__(self, key):
        val = self.get(key)
        if val is None:
            raise KeyError(f"Configuration for {key!r} not found")
        return val
