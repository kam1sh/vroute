import cleo
from cleo import formatters

__version__ = "0.1.0"


class VRoute:
    def __init__(self):
        self.cfg = None
        self.db = None

    def read_config(self, file=None):
        from . import cfg

        self.cfg = cfg.Configuration(from_file=file)

    def load_db(self, file=None, debug=None):
        from . import db

        file = file or self.cfg.db_url
        debug = debug or self.cfg.db_debug
        self.db = db.Database(file=file, debug=debug, auto_create=True)
