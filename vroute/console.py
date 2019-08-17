"""Cleo stuff"""

from cleo import formatters, Application as BaseApplication
from . import VRoute, __version__, commands
from .logger import logger

class Application(BaseApplication):
    def __init__(self):
        super().__init__(name="VPN network router", version=__version__)
        # poetry-like errors formatter
        self.add(commands.AddRecord())
        self.vroute: VRoute = None


    def prepare(self, cfg=None, db=None):
        self.vroute = VRoute()
        self.vroute.read_config(file=cfg)
        debug = logger.is_debug()
        self.vroute.load_db(file=db, debug=debug)

    def do_run(self, input_, output_) -> int:
        self.prepare()
        with self.vroute:
            return super().do_run(input_, output_)

def main():
    app = Application()
    app.run(output_=logger)
