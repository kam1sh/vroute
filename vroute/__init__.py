import logging
import os
from pathlib import Path

import requests

__version__ = "0.4.1"

log = logging.getLogger(__name__)


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

    def request(self, method, url, params=None, data=None, json=None, check_resp=True):
        response = requests.request(
            method,
            url=f"http://localhost:{self.cfg.listen_port}{url}",
            params=params,
            data=data,
            json=json,
        )
        if check_resp and not response.ok:
            log.debug("Request info:\nparams: %s\ndata: %s", params, data)
            raise ValueError(f"Error executing request {method} {url}")
        return response

    def load_db(self, file=None, debug=False):
        if not self.db:
            from . import db

            file = file or self.cfg.db_file
            debug = debug or self.cfg.db_debug
            self.db = db.Database(file=file, debug=debug, auto_create=True)

    def serve(self, webapp):
        if webapp is None:
            raise ValueError("Web application is not initialized.")
        from aiohttp import web

        # run with the lock file
        with self:
            web.run_app(webapp, host="127.0.0.1", port=1015)

    def __enter__(self):
        lock = self.cfg.lock_file
        log.debug("Obtaining lock file <comment>%s</>", lock)
        if lock.exists():
            raise EnvironmentError(f"Lock file {lock} exists.")
        self.lock = lock.open("w")

    def __exit__(self, exc_type, value, tb):
        log.debug("Releasing lock file")
        self.lock.close()
        self.cfg.lock_file.unlink()
