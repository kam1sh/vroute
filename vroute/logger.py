import enum
import logging
import os

from cleo.outputs import Output, ConsoleOutput


class Level(enum.IntEnum):
    ALL = 1
    VERBOSE = 2
    INFO = 3
    DEBUG = 4

    def as_logging(self):
        return _logging_levels[self.value]

    def as_clikit(self):
        return _clikit_levels[self.value]


_logging_levels = {1: logging.INFO, 2: logging.INFO, 3: logging.DEBUG, 4: logging.DEBUG}

_clikit_levels = {
    1: Output.VERBOSITY_NORMAL,
    2: Output.VERBOSITY_VERBOSE,
    3: Output.VERBOSITY_VERY_VERBOSE,
    4: Output.VERBOSITY_DEBUG,
}


class Logger(ConsoleOutput):
    test_log: logging.Logger

    def __init__(self, name=None):
        super().__init__()
        self.test_log = logging.getLogger(name or "console")

    def log(self, msg, *args):
        """ Prints line on the screen. """
        self._log(msg, Level.ALL, args)

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
        if "PYTEST_CURRENT_TEST" in os.environ:
            self.test_log.log(level.as_logging(), msg, *args)
        elif self.verbosity >= level.as_clikit():
            self.writeln(msg % args)


logger = Logger()

log = logger.log
verbose = logger.verbose
debug = logger.debug
