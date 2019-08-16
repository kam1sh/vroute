import cleo
from cleo import formatters
from . import cfg, db

__version__ = "0.1.0"

class VRoute:
    def __init__(self):
        self.cfg = None
        self.db = None

    def read_config(self, file=None):
        self.cfg = cfg.Configuration(from_file=file)

    def load_db(self, file=None, debug=None):
        file = file or self.cfg.get("db.file")
        debug = debug or self.cfg.get("db.debug")
        self.db = db.Database(file=file, debug=debug, auto_create=True)


class Application(cleo.Application):
    def __init__(self):
        super().__init__(name="Network servant", version=__version__)
        # poetry-like errors formatter
        self._formatter = formatters.Formatter(True)
        self._formatter.add_style("error", "red", options=["bold"])
        self.vroute = None

    def render_exception(self, e, output_):
        # patch output formatter to our own
        output_.get_formatter = lambda: self._formatter
        return super().render_exception(e, output_)

    def do_run(self, input_, output_):
        self.vroute = VRoute()
        self.vroute.read_config()
        self.vroute.load_db()

        return super().do_run(input_, output_)
