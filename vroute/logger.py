import enum
import io

from cleo.outputs import Output, ConsoleOutput, StreamOutput
from cleo import formatters


class Level(enum.IntEnum):
    ALL = 1
    VERBOSE = 2
    INFO = 3
    DEBUG = 4

    def as_clikit(self):
        return _clikit_levels[self.value]


_clikit_levels = {
    1: Output.VERBOSITY_NORMAL,
    2: Output.VERBOSITY_VERBOSE,
    3: Output.VERBOSITY_VERY_VERBOSE,
    4: Output.VERBOSITY_DEBUG,
}


class Logger(ConsoleOutput):
    def __init__(self):
        super().__init__()
        # formatter that mimics poetry style
        formatter = formatters.Formatter(True)
        formatter.add_style("error", "red", options=["bold"])
        self.set_formatter(formatter)
        self._tee = None

    def enable_storage(self):
        """ Enables log storage for testing purposes. """
        self._tee = StreamOutput(io.BytesIO())

    def display_output(self):
        writer = self._tee.get_stream()
        writer.seek(0)
        display = writer.read().decode("utf-8")
        return display

    def log(self, msg, *args):
        """ Prints line on the screen. """
        self._log(msg, Level.ALL, args)
        if self._tee is not None:
            self._tee.writeln(msg % args)

    def info(self, msg, *args):
        """ Prints line on the screen with the level `INFO`. """
        self._log(msg, Level.INFO, args)

    def verbose(self, msg, *args):
        """ Prints line on the screen with the level `VERBOSE`. """
        self._log(msg, Level.VERBOSE, args)

    def debug(self, msg, *args):
        """ Prints line on the screen with the level `DEBUG`. """
        self._log(msg, Level.DEBUG, args)

    def _log(self, msg, level, args):
        if self.verbosity >= level.as_clikit():
            self.writeln(msg % args)

logger = Logger()

log = logger.log
info = logger.info
verbose = logger.verbose
debug = logger.debug
