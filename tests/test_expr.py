from functools import reduce

from hypothesis import given, assume, settings
from hypothesis import strategies as st

from pyparsec.Char import char, digit
from pyparsec.Combinators import many1
from pyparsec.Expr import Assoc, Infix, Prefix, build_expression_parser
from pyparsec.Prim import run_parser


def _build_arithmetic_parser():
    integer = many1(digit()).map(lambda d: int("".join(d)))

    def add(x, y):
        return x + y

    def sub(x, y):
        return x - y

    def mul(x, y):
        return x * y

    def div(x, y):
        return x // y

    def neg(x):
        return -x

    table = [
        [Prefix(char("-").map(lambda _: neg))],
        [
            Infix(char("*").map(lambda _: mul), Assoc.LEFT),
            Infix(char("/").map(lambda _: div), Assoc.LEFT),
        ],
        [
            Infix(char("+").map(lambda _: add), Assoc.LEFT),
            Infix(char("-").map(lambda _: sub), Assoc.LEFT),
        ],
    ]

    return build_expression_parser(table, integer)


@given(
    st.lists(st.integers(min_value=1, max_value=9), min_size=2, max_size=6),
    st.lists(
        st.sampled_from(["+", "-", "*"]),
        min_size=1,
        max_size=5,
    ),
)
@settings(deadline=None)
def test_prop_arithmetic_precedence(nums, ops):
    """Property: parsing an expression string gives the same result as Python eval."""
    assume(len(ops) == len(nums) - 1)

    expr_parser = _build_arithmetic_parser()

    # Build expression string: "3+2*4-1"
    expr_str = str(nums[0])
    for op, n in zip(ops, nums[1:]):
        expr_str += op + str(n)

    res, err = run_parser(expr_parser, expr_str)
    expected = eval(expr_str)  # Safe: only digits and +-*

    assert err is None
    assert res == expected


@given(st.lists(st.integers(min_value=1, max_value=9), min_size=2, max_size=6))
@settings(deadline=None)
def test_prop_left_associativity(nums):
    """Property: subtraction is left-associative — a-b-c == (a-b)-c."""
    expr_parser = _build_arithmetic_parser()

    expr_str = "-".join(str(n) for n in nums)
    res, err = run_parser(expr_parser, expr_str)

    # Left-fold subtraction
    expected = reduce(lambda a, b: a - b, nums)

    assert err is None
    assert res == expected


@given(st.lists(st.integers(min_value=1, max_value=9), min_size=1, max_size=4))
@settings(deadline=None)
def test_prop_prefix_negation(nums):
    """Property: prefix negation applies before other operations."""
    expr_parser = _build_arithmetic_parser()

    # Build: -a*b+c...
    expr_str = "-" + str(nums[0])
    if len(nums) > 1:
        expr_str += "+" + "+".join(str(n) for n in nums[1:])

    res, err = run_parser(expr_parser, expr_str)
    expected = -nums[0] + sum(nums[1:])

    assert err is None
    assert res == expected


@given(st.lists(st.integers(min_value=1, max_value=2), min_size=2, max_size=3))
@settings(deadline=None)
def test_prop_right_associativity(bases):
    """Property: ^ is right-associative — a^b^c == a^(b^c)."""
    integer = many1(digit()).map(lambda d: int("".join(d)))

    def power(x, y):
        return x ** y

    table = [[Infix(char("^").map(lambda _: power), Assoc.RIGHT)]]
    expr = build_expression_parser(table, integer)

    expr_str = "^".join(str(b) for b in bases)
    res, err = run_parser(expr, expr_str)

    # Right-fold exponentiation
    expected = reduce(lambda a, b: b ** a, reversed(bases))

    assert err is None
    assert res == expected
