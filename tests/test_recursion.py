import sys

from hypothesis import given, settings
from hypothesis import strategies as st

from pyparsec.Char import char
from pyparsec.Prim import many, run_parser


@given(st.integers(min_value=500, max_value=5000))
@settings(deadline=None)
def test_prop_stack_safety(n):
    sys.setrecursionlimit(1000)
    input_str = "a" * n
    parser = many(char("a"))
    res, err = run_parser(parser, input_str)
    assert err is None
    assert len(res) == n
