import logging
import os
import typing as ty
from pathlib import Path

import requests

from .routing import Manager
from .services import NetworkingService

__version__ = "0.5.2"

log = logging.getLogger(__name__)


class VRoute:
    network_service: NetworkingService

    def __init__(self):
        self.cfg = None
        self.db = None
        self.lock = None
        self.psql_config = None
        self.netlink = None
        self.ros = None
        self.network_service = None

    def connect(self):
        from .routing import LinuxRouteManager, RouterosManager

        self.netlink = LinuxRouteManager.fromconf(self.cfg)
        ros = self.cfg.get("routeros")
        self.ros = RouterosManager.fromconf(ros)
        self.network_service = NetworkingService(self.psql_config)

    def disconnect(self):
        self.netlink.close()
        self.ros.disconnect()

    def read_config(self, file=None):
        from . import cfg

        # environment variable has the second priority
        file = file or os.getenv("VROUTE_CONFIG")
        file = Path(file) if file else Path.home() / ".config/vroute.yml"
        self.cfg = cfg.Configuration(from_file=file)
        self.psql_config = self.cfg["postgresql"]

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

    @property
    def managers(self) -> ty.Collection[Manager]:
        return (self.netlink, self.ros)
