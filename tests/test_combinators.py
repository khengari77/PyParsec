from functools import reduce

from hypothesis import given, assume
from hypothesis import strategies as st

from pyparsec.Char import any_char, char, digit, string
from pyparsec.Combinators import *
from pyparsec.Parsec import Ok, State, initial_pos
from pyparsec.Prim import many1, run_parser


def run(parser, input_str):
    return run_parser(parser, input_str)


# --- Choice ---


@given(st.sampled_from("abc"))
def test_prop_choice_match(c):
    """Property: choice matches any of the given parsers."""
    p = choice([char("a"), char("b"), char("c")])
    res, err = run(p, c)
    assert res == c
    assert err is None


@given(st.characters().filter(lambda c: c not in "abc"))
def test_prop_choice_miss(c):
    """Property: choice fails when no parser matches, error mentions all alternatives."""
    p = choice([char("a"), char("b"), char("c")])
    res, err = run(p, c)
    assert res is None
    msg = str(err)
    assert "'a'" in msg and "'b'" in msg and "'c'" in msg


def test_choice_empty():
    res, err = run(choice([]), "input")
    assert res is None
    assert "no alternatives" in str(err)


# --- Count ---


@given(st.integers(min_value=0, max_value=20))
def test_prop_count(n):
    """Property: count(n, p) succeeds when input has enough, fails when short."""
    # Success case
    input_str = "a" * n + "b"
    p = count(n, char("a"))
    res, err = run(p, input_str)
    assert res == ["a"] * n
    assert err is None

    # Failure case: one fewer than needed (when n > 0)
    if n > 0:
        short_input = "a" * (n - 1)
        res_fail, err_fail = run(p, short_input)
        assert res_fail is None
        assert err_fail is not None


# --- Option / Between ---


@given(st.text(min_size=1, max_size=10), st.booleans())
def test_prop_option(default, match):
    """Property: option returns parsed value on match, default on miss."""
    p = option(default, char("a"))
    if match:
        res, err = run(p, "a")
        assert res == "a"
        assert err is None
    else:
        res, err = run(p, "b")
        assert res == default
        assert err is None


@given(st.characters())
def test_prop_option_maybe(c):
    """Property: option_maybe returns value on match, None on miss."""
    p = option_maybe(char(c))
    res, err = run(p, c)
    assert res == c
    assert err is None

    diff = chr((ord(c) + 1) % 0x10000)
    if diff != c:
        res_miss, err_miss = run(p, diff)
        assert res_miss is None
        assert err_miss is None


@given(
    st.sampled_from("([{<"),
    st.sampled_from(")]}>"),
    st.text(min_size=1, max_size=5, alphabet=st.sampled_from("abcde")),
)
def test_prop_between(open_c, close_c, content):
    """Property: between extracts content from delimiters."""
    assume(open_c != close_c)
    assume(all(c not in content for c in [open_c, close_c]))
    p = between(char(open_c), char(close_c), string(content))
    res, err = run(p, open_c + content + close_c)
    assert res == content
    assert err is None


# --- Repetition (many1, sep_by, etc) ---


@given(st.integers(min_value=0, max_value=20))
def test_prop_many1(n):
    """Property: many1 requires at least 1 match."""
    p = many1(char("a"))
    input_str = "a" * n + "b"
    res, err = run(p, input_str)
    if n >= 1:
        assert res == ["a"] * n
        assert err is None
    else:
        assert res is None


@given(st.integers(min_value=0, max_value=10))
def test_prop_sep_by(n):
    """Property: sep_by parses n items separated by commas, including zero."""
    p = sep_by(char("a"), char(","))
    if n == 0:
        res, err = run(p, "")
        assert res == []
        assert err is None
    else:
        input_str = ",".join(["a"] * n)
        res, err = run(p, input_str)
        assert res == ["a"] * n
        assert err is None


@given(st.integers(min_value=0, max_value=10))
def test_prop_sep_by1(n):
    """Property: sep_by1 requires at least one match."""
    p = sep_by1(char("a"), char(","))
    if n == 0:
        res, err = run(p, "")
        assert res is None
    else:
        input_str = ",".join(["a"] * n)
        res, err = run(p, input_str)
        assert res == ["a"] * n
        assert err is None


@given(st.integers(min_value=0, max_value=10))
def test_prop_end_by(n):
    """Property: end_by parses items each followed by separator."""
    p = end_by(char("a"), char(";"))
    input_str = "a;" * n
    res, err = run(p, input_str)
    assert res == ["a"] * n
    assert err is None


@given(st.integers(min_value=0, max_value=10), st.booleans())
def test_prop_sep_end_by(n, trailing):
    """Property: sep_end_by allows optional trailing separator."""
    p = sep_end_by(char("a"), char(";"))
    if n == 0:
        res, err = run(p, "")
        assert res == []
        assert err is None
    else:
        input_str = ";".join(["a"] * n)
        if trailing:
            input_str += ";"
        res, err = run(p, input_str)
        assert res == ["a"] * n
        assert err is None


@given(st.integers(min_value=1, max_value=10))
def test_prop_end_by1(n):
    """Property: end_by1 requires at least one item followed by separator."""
    p = end_by1(char("a"), char(";"))
    input_str = "a;" * n
    res, err = run(p, input_str)
    assert res == ["a"] * n
    assert err is None


@given(st.just(""))
def test_prop_end_by1_empty(s):
    """Property: end_by1 fails on empty input."""
    p = end_by1(char("a"), char(";"))
    res, err = run(p, s)
    assert res is None
    assert err is not None


@given(st.integers(min_value=1, max_value=10), st.booleans())
def test_prop_sep_end_by1(n, trailing):
    """Property: sep_end_by1 requires at least one, optional trailing sep."""
    p = sep_end_by1(char("a"), char(";"))
    input_str = ";".join(["a"] * n)
    if trailing:
        input_str += ";"
    res, err = run(p, input_str)
    assert res == ["a"] * n
    assert err is None


@given(st.just(""))
def test_prop_sep_end_by1_empty(s):
    """Property: sep_end_by1 fails on empty input."""
    p = sep_end_by1(char("a"), char(";"))
    res, err = run(p, s)
    assert res is None
    assert err is not None


# --- Expression Chains (Associativity) ---


@given(st.lists(st.integers(min_value=1, max_value=9), min_size=2, max_size=6))
def test_prop_chainl1(nums):
    """Property: chainl1 with subtraction is left-associative."""
    def sub(x, y):
        return x - y

    num = digit().map(int)
    op = char("-").map(lambda _: sub)
    expr = chainl1(num, op)

    input_str = "-".join(str(n) for n in nums)
    res, err = run(expr, input_str)

    expected = reduce(lambda a, b: a - b, nums)
    assert err is None
    assert res == expected


@given(st.lists(st.integers(min_value=1, max_value=2), min_size=2, max_size=3))
def test_prop_chainr1(bases):
    """Property: chainr1 with exponentiation is right-associative."""
    def power(x, y):
        return x ** y

    num = digit().map(int)
    op = char("^").map(lambda _: power)
    expr = chainr1(num, op)

    input_str = "^".join(str(b) for b in bases)
    res, err = run(expr, input_str)

    expected = reduce(lambda a, b: b ** a, reversed(bases))
    assert err is None
    assert res == expected


@given(st.integers(min_value=-100, max_value=100))
def test_prop_chain_default(default):
    """Property: chainl/chainr fall back to default on empty input."""
    num = digit().map(int)
    op = char("+").map(lambda _: lambda x, y: x + y)

    res_l, err_l = run(chainl(num, op, default), "")
    assert res_l == default
    assert err_l is None

    res_r, err_r = run(chainr(num, op, default), "")
    assert res_r == default
    assert err_r is None


# --- EOF / Not Followed By ---


@given(st.characters())
def test_prop_eof(c):
    """Property: eof succeeds at end of input, fails when input remains."""
    p = char(c) >> (lambda _: eof())

    # Exact match: eof succeeds
    res, err = run(p, c)
    assert err is None

    # Extra input: eof fails
    res2, err2 = run(p, c + "x")
    assert res2 is None
    assert "end of input" in str(err2)


@given(
    st.text(min_size=1, max_size=5, alphabet=st.sampled_from("abcde")),
    st.characters(whitelist_categories=("L",)),
)
def test_prop_not_followed_by(keyword, suffix):
    """Property: not_followed_by rejects when suffix matches, accepts otherwise."""
    p = string(keyword) < not_followed_by(char(suffix))

    # Should fail when followed by the forbidden suffix
    res_fail, _ = run(p, keyword + suffix)
    assert res_fail is None

    # Should succeed when followed by something else
    other = chr((ord(suffix) + 1) % 0x10000)
    if other != suffix:
        res_ok, err_ok = run(p, keyword + other)
        assert res_ok == keyword
        assert err_ok is None


@given(st.text(min_size=0, max_size=20, alphabet=st.sampled_from("abcde .!?")))
def test_prop_many_till(content):
    """Property: many_till collects chars until end marker is found."""
    p = between(
        string("<!--"),
        string("-->"),
        many_till(any_char(), look_ahead(string("-->"))),
    )
    input_str = "<!--" + content + "-->"
    assume("-->" not in content)
    res, err = run(p, input_str)
    assert "".join(res) == content
    assert err is None


# --- Optional / Skip ---


@given(st.characters())
def test_prop_optional(c):
    """Property: optional() returns None whether inner parser succeeds or fails."""
    p = optional(char(c))

    # Match: returns None (discards result)
    res, err = run(p, c)
    assert res is None
    assert err is None

    # Miss: also returns None
    diff = chr((ord(c) + 1) % 0x10000)
    if diff != c:
        res2, err2 = run(p, diff)
        assert res2 is None
        assert err2 is None


@given(st.integers(min_value=0, max_value=10))
def test_prop_skip_many1(n):
    """Property: skip_many1 succeeds with 1+ matches, fails with 0."""
    p = skip_many1(char("a"))
    input_str = "a" * n + "b"
    res, err = run(p, input_str)
    if n >= 1:
        assert res is None
        assert err is None
    else:
        assert res is None
        assert err is not None


# --- any_token ---


@given(st.lists(st.integers(), min_size=1))
def test_prop_any_token(tokens):
    """Property: any_token returns the first token including falsy values."""
    p = any_token()
    state = State(tokens, initial_pos("test"), None)
    res = p(state)
    assert isinstance(res.reply, Ok)
    assert res.value == tokens[0]


def test_any_token_falsy_cases_explicit():
    """Explicitly test the falsy cases that would fail with original bug"""
    test_cases = [
        [0, 1, 2],  # Zero
        [False, True],  # False
        ["", "a"],  # Empty string
    ]
    for case in test_cases:
        p = any_token()
        state = State(case, initial_pos("test"), None)
        res = p(state)
        assert isinstance(res.reply, Ok)
        assert res.value == case[0]
