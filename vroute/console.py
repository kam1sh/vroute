"""Cleo stuff"""

from cleo import formatters, Application as BaseApplication
from . import VRoute, __version__, commands, logger


class Application(BaseApplication):
    def __init__(self):
        super().__init__(name="VPN network router", version=__version__)
        # poetry-like errors formatter
        self._formatter = formatters.Formatter(True)
        self._formatter.add_style("error", "red", options=["bold"])
        self.vroute = None

    def prepare(self, cfg=None, db=None):
        self.vroute = VRoute()
        self.vroute.read_config(file=cfg)
        self.vroute.load_db(file=db)

    def render_exception(self, e, output_):
        # patch output formatter to our own
        output_.get_formatter = lambda: self._formatter
        return super().render_exception(e, output_)

    def do_run(self, input_, output_):
        self.prepare()
        return super().do_run(input_, output_)


app = Application()
app.add(commands.AddRecord())


def main():
    output = logger.logger
    app.run(output_=output)
