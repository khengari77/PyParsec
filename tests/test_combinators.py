import pytest
from hypothesis import given, strategies as st
from pyparsec.Parsec import State, initial_pos, Ok, Error
from pyparsec.Prim import run_parser, pure
from pyparsec.Char import char, string, digit, any_char
from pyparsec.Combinators import (
    choice, count, between, option, option_maybe, optional,
    many1, skip_many1, sep_by, sep_by1, end_by,
    sep_end_by, chainl1, chainr1, eof, not_followed_by, many_till, look_ahead,
)

def run(parser, input_str):
    return run_parser(parser, input_str)

# --- Choice ---

def test_choice_basic():
    # Matches first available
    p = choice([char('a'), char('b'), char('c')])
    assert run(p, "a")[0] == "a"
    assert run(p, "b")[0] == "b"
    assert run(p, "c")[0] == "c"
    
    # Fails if none match
    res, err = run(p, "d")
    assert res is None
    # Error should contain info about all expectations
    msg = str(err)
    assert "'a'" in msg and "'b'" in msg and "'c'" in msg

def test_choice_empty():
    res, err = run(choice([]), "input")
    assert res is None
    assert "no alternatives" in str(err)

# --- Count ---

@given(st.integers(min_value=0, max_value=20))
def test_count(n):
    input_str = "a" * n + "b"
    p = count(n, char('a'))
    res, err = run(p, input_str)
    
    assert res == ['a'] * n
    assert err is None

def test_count_fail():
    # Expect 3, get 2
    p = count(3, char('a'))
    res, err = run(p, "aa")
    assert res is None
    assert err is not None

# --- Option / Between ---

def test_option():
    p = option("default", string("foo"))
    assert run(p, "foo")[0] == "foo"
    assert run(p, "bar")[0] == "default"

def test_option_maybe():
    p = option_maybe(char('a'))
    assert run(p, "a")[0] == 'a'
    assert run(p, "b")[0] is None

def test_between():
    p = between(char('('), char(')'), string("foo"))
    res, _ = run(p, "(foo)")
    assert res == "foo"
    
    # Fail closing
    res_fail, _ = run(p, "(foo")
    assert res_fail is None

# --- Repetition (many1, sep_by, etc) ---

def test_many1():
    p = many1(char('a'))
    assert run(p, "aaa")[0] == ['a', 'a', 'a']
    assert run(p, "a")[0] == ['a']
    
    # Fails on 0
    res, _ = run(p, "b")
    assert res is None

def test_sep_by():
    # a,a,a
    p = sep_by(char('a'), char(','))
    
    assert run(p, "a,a,a")[0] == ['a', 'a', 'a']
    assert run(p, "a")[0] == ['a']
    assert run(p, "")[0] == [] # Zero matches is ok for sep_by

def test_sep_by1():
    p = sep_by1(char('a'), char(','))
    assert run(p, "")[0] is None # Must have at least one

def test_end_by():
    # a;a;a;
    p = end_by(char('a'), char(';'))
    assert run(p, "a;a;")[0] == ['a', 'a']
    assert run(p, "")[0] == []

def test_sep_end_by():
    # Allows optional trailing separator
    p = sep_end_by(char('a'), char(';'))
    
    assert run(p, "a;a")[0] == ['a', 'a']   # sep_by style
    assert run(p, "a;a;")[0] == ['a', 'a']  # end_by style
    assert run(p, "")[0] == []

# --- Expression Chains (Associativity) ---

def test_chainl1_associativity():
    # Subtraction is Left Associative: 10 - 5 - 2
    # (10 - 5) - 2 = 3
    # NOT 10 - (5 - 2) = 7
    
    def sub(x, y): return x - y
    
    # Parser: digit op digit op digit
    num = digit().map(int)
    op = char('-').map(lambda _: sub)
    
    expr = chainl1(num, op)
    
    res, _ = run(expr, "9-3-2")
    assert res == 4 # (9-3)-2 = 6-2 = 4

def test_chainr1_associativity():
    # Power is Right Associative: 2 ^ 3 ^ 2
    # 2 ^ (3 ^ 2) = 2 ^ 9 = 512
    # NOT (2 ^ 3) ^ 2 = 8 ^ 2 = 64
    
    def power(x, y): return x ** y
    
    num = digit().map(int)
    op = char('^').map(lambda _: power)
    
    expr = chainr1(num, op)
    
    res, _ = run(expr, "2^3^2")
    assert res == 512

# --- EOF / Not Followed By ---

def test_eof():
    p = char('a') >> (lambda _: eof())
    
    assert run(p, "a")[0] is None # Success (returns None)
    
    res, err = run(p, "ab")
    assert res is None
    assert "end of input" in str(err)

def test_not_followed_by():
    # Keyword 'let' cannot be followed by alphanumeric (e.g. 'lets')
    keyword_let = string("let") < not_followed_by(char('s'))
    
    assert run(keyword_let, "let ")[0] == "let"
    
    res, _ = run(keyword_let, "lets")
    assert res is None

def test_many_till():
    # Parsing comment: <!-- content -->
    p = between(
        string("<!--"), 
        string("-->"), 
        many_till(any_char(), look_ahead(string("-->")))
    )
    
    input_str = "<!--hello world-->"
    res, _ = run(p, input_str)
    assert "".join(res) == "hello world"
