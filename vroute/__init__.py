from pathlib import Path
import cleo
from cleo import formatters
from .logger import debug
import os

__version__ = "0.3.0"


class VRoute:
    def __init__(self):
        self.cfg = None
        self.db = None
        self.lock = None

    def new_session(self):
        if self.db is None:
            raise EnvironmentError("Database is not configured yet.")
        return self.db.new_session()

    def read_config(self, file=None):
        from . import cfg
        # environment variable has the second priority
        file = file or os.getenv("VROUTE_CONFIG")
        file = Path(file) if file else Path.home() / ".config/vroute.yml"
        self.cfg = cfg.Configuration(from_file=file)

    def load_db(self, file=None, debug=False):
        from . import db

        file = file or self.cfg.db_file
        debug = debug or self.cfg.db_debug
        self.db = db.Database(file=file, debug=debug, auto_create=True)

    def __enter__(self):
        lock = self.cfg.lock_file
        debug("Obtaining lock file <comment>%s</>", lock)
        if lock.exists():
            raise EnvironmentError(f"Lock file {lock} exists.")
        self.lock = lock.open("w")

    def __exit__(self, exc_type, value, tb):
        debug("Releasing lock file")
        self.lock.close()
        self.cfg.lock_file.unlink()
