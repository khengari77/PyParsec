import pytest
from hypothesis import given, strategies as st
from pyparsec.Parsec import State, SourcePos, ParseResult, Ok, Error, initial_pos
from pyparsec.Char import (
    char, satisfy, one_of, none_of, 
    string, string_prime,
    space, spaces, newline, crlf, end_of_line, tab,
    digit, letter, upper, lower, alpha_num, hex_digit, oct_digit, any_char
)
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
    # string' matches but does NOT consume input
    p = string_prime(s)
    state = State(s + "123", initial_pos("test"), None)
    
    res = p(state)
    
    if isinstance(res.reply, Ok):
        assert res.value == s
        assert not res.consumed  # Crucial for string_prime
        assert res.state.input == s + "123" # Input remains untouched
    else:
        # Should only fail if s is not in input
        pass

# --- Whitespace & Newlines ---

def test_newline_logic():
    # \n
    res, _ = run(newline(), "\n")
    assert res == "\n"
    
    # \r\n (crlf) -> returns \n
    res_crlf, _ = run(crlf(), "\r\n")
    assert res_crlf == "\n"
    
    # end_of_line handles both
    res_eol1, _ = run(end_of_line(), "\n")
    res_eol2, _ = run(end_of_line(), "\r\n")
    assert res_eol1 == "\n"
    assert res_eol2 == "\n"

def test_spaces():
    # Matches zero spaces
    res0, _ = run(spaces(), "abc")
    assert res0 is None # Returns None
    
    # Matches many spaces
    res1, _ = run(spaces(), "   abc")
    assert res1 is None
    
    # Check that it actually consumed input by chaining
    p = spaces() >> char('a')
    res2, _ = run(p, "   a")
    assert res2 == 'a'

def test_tab_position():
    # Parsing a tab should update column by 8 (default)
    # Assuming tab stops at 8, 16, 24...
    p = tab()
    state = State("\t", initial_pos("test"), None)
    
    # 1. Start at 1, 1
    res = p(state)
    assert res.state.pos.column == 9 # 1 + 8
    
    # 2. Start at 1, 5
    state2 = State("\t", SourcePos(1, 5, "test"), None)
    res2 = p(state2)
    # Next tab stop after 5 is 9.
    # Logic: new_col = old + 8 - ((old-1) % 8)
    # 5 + 8 - (4 % 8) = 5 + 8 - 4 = 9. Correct.
    assert res2.state.pos.column == 9

# --- Classification Parsers ---

@given(st.characters(whitelist_categories=('Nd',)))
def test_digit(c):
    res, _ = run(digit(), c)
    assert res == c

@given(st.characters(whitelist_categories=('Ll',)))
def test_lower(c):
    res, _ = run(lower(), c)
    assert res == c

@given(st.characters(whitelist_categories=('Lu',)))
def test_upper(c):
    res, _ = run(upper(), c)
    assert res == c

@given(st.characters(whitelist_categories=('L',)))
def test_letter(c):
    res, _ = run(letter(), c)
    assert res == c

def test_hex_oct():
    assert run(hex_digit(), "a")[0] == 'a'
    assert run(hex_digit(), "F")[0] == 'F'
    assert run(hex_digit(), "9")[0] == '9'
    assert run(hex_digit(), "g")[0] is None
    
    assert run(oct_digit(), "7")[0] == '7'
    assert run(oct_digit(), "8")[0] is None

def test_any_char():
    res, _ = run(any_char(), "?")
    assert res == "?"
    
    # Fails on empty
    res_empty, err = run(any_char(), "")
    assert res_empty is None
    assert err is not None
