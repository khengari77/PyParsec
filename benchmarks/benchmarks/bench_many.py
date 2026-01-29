from pyparsec.Char import char
from pyparsec.Prim import many, run_parser


class TimeMany:
    def setup(self):
        self.parser = many(char("a"))
        self.small = "a" * 1000
        self.medium = "a" * 10000
        self.large = "a" * 100000

    def time_many_small(self):
        run_parser(self.parser, self.small)

    def time_many_medium(self):
        run_parser(self.parser, self.medium)

    def time_many_large(self):
        run_parser(self.parser, self.large)
