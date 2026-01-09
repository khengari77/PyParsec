import sys
from pyparsec.Char import char
from pyparsec.Prim import many, run_parser

def test_stack_safety():
    sys.setrecursionlimit(1000)
    n = 5000
    input_str = "a" * n
    parser = many(char('a'))
    res, err = run_parser(parser, input_str)
    assert err is None
    assert len(res) == n
