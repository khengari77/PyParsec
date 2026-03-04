"""Tests for bulk scanning primitives: take_while, take_while1, skip_while, skip_while1."""

from hypothesis import given
from hypothesis import strategies as st

from pyparsec.Prim import run_parser, take_while, take_while1, skip_while, skip_while1, many
from pyparsec.Char import satisfy


def run(parser, input_str):
    return run_parser(parser, input_str)


# --- take_while ---


def test_take_while_matches_all():
    val, err = run(take_while(str.isdigit), "12345abc")
    assert val == "12345"
    assert err is None


def test_take_while_matches_none():
    val, err = run(take_while(str.isdigit), "abc")
    assert val == ""
    assert err is None


def test_take_while_empty_input():
    val, err = run(take_while(str.isdigit), "")
    assert val == ""
    assert err is None


def test_take_while_matches_entire_input():
    val, err = run(take_while(str.isalpha), "hello")
    assert val == "hello"
    assert err is None


# --- take_while1 ---


def test_take_while1_matches():
    val, err = run(take_while1(str.isdigit), "123abc")
    assert val == "123"
    assert err is None


def test_take_while1_fails_no_match():
    val, err = run(take_while1(str.isdigit), "abc")
    assert val is None
    assert err is not None


def test_take_while1_fails_empty():
    val, err = run(take_while1(str.isdigit), "")
    assert val is None
    assert err is not None


# --- skip_while ---


def test_skip_while_skips():
    from pyparsec.Char import char

    p = skip_while(str.isspace) >> char("a")
    val, err = run(p, "   a")
    assert val == "a"
    assert err is None


def test_skip_while_nothing_to_skip():
    from pyparsec.Char import char

    p = skip_while(str.isspace) >> char("a")
    val, err = run(p, "a")
    assert val == "a"
    assert err is None


# --- skip_while1 ---


def test_skip_while1_skips():
    from pyparsec.Char import char

    p = skip_while1(str.isspace) >> char("a")
    val, err = run(p, "   a")
    assert val == "a"
    assert err is None


def test_skip_while1_fails_no_match():
    val, err = run(skip_while1(str.isspace), "abc")
    assert val is None
    assert err is not None


# --- Position tracking ---


def test_take_while_tracks_newlines():
    val, err = run(take_while(lambda c: c != "x"), "ab\ncd\nef")
    assert val == "ab\ncd\nef"
    assert err is None


def test_take_while_stops_before_newline():
    val, err = run(take_while(str.isalpha), "abc\ndef")
    assert val == "abc"
    assert err is None


# --- Property-based: equivalence with many(satisfy(...)) ---


@given(st.text(alphabet=st.characters(categories=("L", "N", "P", "S")), min_size=0, max_size=50))
def test_take_while_equivalent_to_many_satisfy(text):
    pred = str.isalpha
    val_bulk, err_bulk = run(take_while(pred), text)
    val_many, err_many = run(many(satisfy(pred)).map("".join), text)
    assert val_bulk == val_many


@given(st.text(alphabet=st.characters(categories=("L", "N", "P", "S")), min_size=0, max_size=50))
def test_take_while1_equivalent_to_many1_satisfy(text):
    from pyparsec.Prim import many1

    pred = str.isalpha
    val_bulk, err_bulk = run(take_while1(pred), text)
    val_many, err_many = run(many1(satisfy(pred)).map("".join), text)
    # Both should succeed or both should fail
    assert (val_bulk is None) == (val_many is None)
    if val_bulk is not None:
        assert val_bulk == val_many
