import cleo
from functools import partial
from more_itertools import chunked

from vroute.logger import debug


class CommandTester(cleo.CommandTester):
    def run(self, args):
        args = list(chunked(args.split(), 2))
        for i, val in enumerate(args):
            args[i] = tuple(val)
        debug("[CommandTester] args: %s" % args)
        self.execute([("command", self._command.get_name())] + args)
