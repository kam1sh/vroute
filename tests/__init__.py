import cleo


class CommandTester(cleo.CommandTester):
    def run(self, *args):
        self.set_inputs(args)
        self.execute([("command", self._command.get_name())])
