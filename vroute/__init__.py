import logging
import os
from pathlib import Path

import requests


__version__ = "0.5.2"

log = logging.getLogger(__name__)


class VRoute:
    def __init__(self):
        self.cfg = None
        self.db = None
        self.lock = None
        self.netlink = None
        self.ros = None

    def connect(self):
        from .routing import RouteManager, RouterosManager

        self.netlink = RouteManager.fromconf(self.cfg)
        ros = self.cfg.get("routeros")
        self.ros = RouterosManager.fromconf(ros)

    def disconnect(self):
        self.netlink.close()
        self.ros.disconnect()

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
