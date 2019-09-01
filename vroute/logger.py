import enum
import io
import logging

import click
from cleo.outputs import Output, ConsoleOutput, StreamOutput
from cleo import formatters


class Level(enum.IntEnum):
    NORMAL = 1
    VERBOSE = 2
    INFO = 3
    DEBUG = 4


class Logger(ConsoleOutput):
    def __init__(self):
        super().__init__()
        self.level = Level.NORMAL
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
        self._log(msg, Level.NORMAL, args)
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
        if self.level >= level:
            click.echo(msg % args)


logger = Logger()

log = logger.log
info = logger.info
verbose = logger.verbose
debug = logger.debug
