import cleo
from cleo import formatters
from . import cfg, db

__version__ = "0.1.0"

class Application(cleo.Application):
    def __init__(self):
        super().__init__(name="Network servant", version=__version__)
        # poetry-like errors formatter
        self._formatter = formatters.Formatter(True)
        self._formatter.add_style("error", "red", options=["bold"])
        self.db = None

    def load_db(self, url, debug=False):
        self.db = db.Database(url=url, debug=debug)

    def render_exception(self, e, output_):
        # patch output formatter to our own
        output_.get_formatter = lambda: self._formatter
        return super().render_exception(e, output_)

    def do_run(self, input_, output_):
        settings = cfg.Configuration()
        self.load_db(settings.db_url, settings.db_debug)
        return super().do_run(input_, output_)
