import cleo


class CommandTester(cleo.CommandTester):
    def execute(self, input_, options=None, verbosity=cleo.Output.VERBOSITY_DEBUG):
        options = options or {}
        options["verbosity"] = verbosity
        return super().execute(input_, options=options)
