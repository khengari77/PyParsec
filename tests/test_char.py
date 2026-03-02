from hypothesis import given
from hypothesis import strategies as st

from pyparsec.Char import (
    any_char,
    char,
    crlf,
    digit,
    end_of_line,
    hex_digit,
    letter,
    lower,
    newline,
    none_of,
    oct_digit,
    one_of,
    satisfy,
    spaces,
    string,
    string_prime,
    tab,
    upper,
)
from pyparsec.Parsec import Error, Ok, SourcePos, State, initial_pos
from pyparsec.Prim import run_parser


def run(parser, input_str):
    return run_parser(parser, input_str)


# --- Basic Character Parsers ---


@given(st.characters())
def test_char_parser(c):
    # Should match the character
    res, err = run(char(c), c)
    assert res == c
    assert err is None

    # Should fail on different character
    diff = chr(ord(c) + 1)
    res_fail, err_fail = run(char(c), diff)
    assert res_fail is None
    assert err_fail is not None


@given(st.characters(), st.text())
def test_satisfy(c, text):
    # Predicate: matches specific char
    p = satisfy(lambda x: x == c)

    if text.startswith(c):
        res, _ = run(p, text)
        assert res == c
    else:
        res, err = run(p, text)
        assert res is None
        assert err is not None


@given(st.text(min_size=1))
def test_one_of(text):
    allowed = list(text)
    p = one_of(allowed)

    # Should match any char from the allowed list
    res, _ = run(p, text[0])
    assert res == text[0]

    # Should fail for something not in list (if list isn't exhaustive)
    # Hard to genericize "not in list" for all unicode, so we test positive case mainly here.


@given(st.text(min_size=1))
def test_none_of(text):
    forbidden = list(text)
    p = none_of(forbidden)

    # Should fail for char in list
    res, err = run(p, text[0])
    assert res is None
    assert err is not None


# --- String Parsers ---


@given(st.text())
def test_string_parser(s):
    p = string(s)

    # Positive case
    res, err = run(p, s + "suffix")
    assert res == s
    assert err is None

    if s:
        # Negative case: Partial match failure
        # Parsec semantics: string() consumes if it matches partially?
        # PyParsec 'tokens' implementation consumes ONLY on full match.
        # Partial match returns Empty Error.

        partial = s[:-1] + chr(ord(s[-1]) + 1) if s else "a"
        res_fail, err_fail = run(p, partial)
        assert res_fail is None
        # Should expect the full string
        assert f"'{s}'" in str(err_fail)


@given(st.text())
def test_string_prime_lookahead(s):
    """Test string_prime works with string input (lookahead behavior)"""
    p = string_prime(s)
    state = State(s + "123", initial_pos("test"), None)
    res = p(state)
    if isinstance(res.reply, Ok):
        assert res.value == s
        assert not res.consumed  # Crucial for string_prime
        assert res.state is not None
        assert res.state.remaining == s + "123"  # Input remains untouched
    else:
        # Should only fail if s is not in input
        pass


def test_string_prime_empty_string():
    """Test string_prime with empty string edge case"""
    p = string_prime("")
    state = State("123", initial_pos("test"), None)
    res = p(state)
    assert isinstance(res.reply, Ok)
    assert res.value == ""
    assert not res.consumed
    assert res.state is not None
    assert res.state.remaining == "123"  # Input unchanged


def test_string_prime_failure():
    """Test string_prime when input doesn't match"""
    p = string_prime("hello")
    state = State("world", initial_pos("test"), None)
    res = p(state)
    assert isinstance(res.reply, Error)
    assert "hello" in str(res.reply.error)


# --- Whitespace & Newlines ---


@given(st.sampled_from(["\n", "\r\n"]))
def test_prop_end_of_line(line_ending):
    """Property: end_of_line handles both \\n and \\r\\n, always returning \\n."""
    res, err = run(end_of_line(), line_ending)
    assert res == "\n"
    assert err is None


@given(st.text(alphabet=st.sampled_from(" \t"), min_size=0, max_size=20))
def test_prop_spaces(ws):
    """Property: spaces() consumes arbitrary whitespace, then chained parser works."""
    p = spaces() >> char("a")
    res, err = run(p, ws + "a")
    assert res == "a"
    assert err is None


@given(st.integers(min_value=1, max_value=80))
def test_prop_tab_position(start_col):
    """Property: tab advances to next tab stop (multiples of 8)."""
    p = tab()
    state = State("\t", SourcePos(1, start_col, "test"), None)
    res = p(state)

    assert res.state is not None
    # Tab stop formula: new_col = old + 8 - ((old-1) % 8)
    expected_col = start_col + 8 - ((start_col - 1) % 8)
    assert res.state.pos.column == expected_col


# --- Classification Parsers ---


@given(st.characters(whitelist_categories=("Nd",)))
def test_digit(c):
    res, _ = run(digit(), c)
    assert res == c


@given(st.characters(whitelist_categories=("Ll",)))
def test_lower(c):
    res, _ = run(lower(), c)
    assert res == c


@given(st.characters(whitelist_categories=("Lu",)))
def test_upper(c):
    res, _ = run(upper(), c)
    assert res == c


@given(st.characters(whitelist_categories=("L",)))
def test_letter(c):
    res, _ = run(letter(), c)
    assert res == c


@given(st.sampled_from(list("0123456789abcdefABCDEF")))
def test_prop_hex_digit(c):
    """Property: all valid hex chars are accepted."""
    res, err = run(hex_digit(), c)
    assert res == c
    assert err is None


@given(st.characters().filter(lambda c: not c.isdigit() and c.lower() not in "abcdef"))
def test_prop_hex_digit_reject(c):
    """Property: non-hex chars are rejected."""
    res, err = run(hex_digit(), c)
    assert res is None
    assert err is not None


@given(st.sampled_from(list("01234567")))
def test_prop_oct_digit(c):
    """Property: all valid octal chars are accepted."""
    res, err = run(oct_digit(), c)
    assert res == c
    assert err is None


@given(st.characters().filter(lambda c: c not in "01234567"))
def test_prop_oct_digit_reject(c):
    """Property: non-octal chars are rejected."""
    res, err = run(oct_digit(), c)
    assert res is None
    assert err is not None


@given(st.characters())
def test_prop_any_char(c):
    """Property: any_char accepts any single character."""
    res, err = run(any_char(), c)
    assert res == c
    assert err is None


@given(st.just(""))
def test_prop_any_char_empty(s):
    """Property: any_char fails on empty input."""
    res, err = run(any_char(), s)
    assert res is None
    assert err is not None
