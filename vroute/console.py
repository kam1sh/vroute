"""Cleo stuff"""
import os

from cleo.outputs import Output
from cleo import formatters, Command, Application as BaseApplication
from . import VRoute, __version__, commands


class Application(BaseApplication):
    def __init__(self):
        super().__init__(name="Network servant", version=__version__)
        # poetry-like errors formatter
        self._formatter = formatters.Formatter(True)
        self._formatter.add_style("error", "red", options=["bold"])
        # TODO create normal proxy?
        self.output: Output = None
        self.vroute = None

    def prepare(self, output, cfg=None, db=None):
        self.output = output
        self.vroute = VRoute()
        self.vroute.read_config(file=cfg)
        self.vroute.load_db(file=db)

    def render_exception(self, e, output_):
        # patch output formatter to our own
        output_.get_formatter = lambda: self._formatter
        return super().render_exception(e, output_)

    def do_run(self, input_, output_):
        self.prepare(output_)
        return super().do_run(input_, output_)

    def writeln(self, msg):
        """ Prints message on the screen. """
        if self.output is None:
            if "PYTEST_CURRENT_TEST" in os.environ:
                return print(msg)
            raise EnvironmentError("Application isn't ready yet.")
        self.output.writeln(msg)


app = Application()
app.add(commands.AddRecord())

writeln = app.writeln

main = app.run
