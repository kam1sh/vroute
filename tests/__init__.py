import asyncio
from shlex import split

import cleo
from functools import partial
from more_itertools import chunked

from vroute.logger import logger


class CommandTester(cleo.CommandTester):
    def run(self, *args):
        args = list(args)
        self.execute([("command", self._command.get_name())] + args)


class DumbFuture(asyncio.Future):
    def __init__(self, value):
        super().__init__()
        self.set_result(value)


class AnswerStub:
    def __init__(self, host, ttl, kind="A"):
        self.host = host
        self.ttl = ttl
        self.type = kind
