import math

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pyparsec.Language import empty_def, java_style, python_style
from pyparsec.Prim import run_parser
from pyparsec.Token import TokenParser


def run(p, s):
    return run_parser(p, s)


# --- Integers (Existing tests + Hypothesis) ---


@given(st.integers())
def test_prop_integers(n):
    lexer = TokenParser(empty_def)
    res, err = run(lexer.integer, str(n))
    assert res == n
    assert err is None


def test_integer_formats():
    lexer = TokenParser(empty_def)
    assert run(lexer.integer, "123")[0] == 123
    assert run(lexer.integer, "+123")[0] == 123
    assert run(lexer.integer, "-123")[0] == -123
    assert run(lexer.integer, "0x1a")[0] == 26
    assert run(lexer.integer, "0o10")[0] == 8


# --- Floats ---


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_prop_floats(f):
    # We convert float to string using standard formatting, which PyParsec should parse
    # Note: Very small/large numbers use scientific notation (e.g. 1e-10), which is supported.
    s = str(f)
    lexer = TokenParser(empty_def)

    # If the string representation looks like an integer (e.g. "123.0" -> "123.0"), it works.
    # If python formats it as "123" (no dot), lexer.float might fail if it strictly requires . or e.
    # Check Token.py logic: float_val requires fraction OR exponent.
    # Python's str(1.0) is "1.0", str(1e20) is "1e+20". These should pass.

    res, err = run(lexer.float, s)

    if err:
        # If it failed, maybe it didn't look like a float?
        # e.g. if st.floats generates 5.0 but str() outputs 5? (Python usually keeps .0)
        pytest.fail(f"Failed to parse float {f} from string '{s}': {err}")

    # Compare with tolerance for floating point arithmetic
    assert math.isclose(res, f, rel_tol=1e-9)


def test_float_edge_cases():
    lexer = TokenParser(empty_def)

    # Standard
    assert run(lexer.float, "3.14")[0] == 3.14
    assert run(lexer.float, "-3.14")[0] == -3.14
    assert run(lexer.float, "0.5")[0] == 0.5

    # Scientific
    assert run(lexer.float, "1e10")[0] == 1e10
    assert run(lexer.float, "1.5e-2")[0] == 0.015
    assert run(lexer.float, "1E+2")[0] == 100.0

    # Ambiguity checks
    # "1" is an integer, NOT a float in Parsec's strict definition usually
    # Our implementation: float_val = decimal . (fraction | exponent)
    res, err = run(lexer.float, "1")
    assert res is None  # Should fail because it lacks . or e

    # "1." is often allowed in Python, let's see our logic:
    # fraction = char('.') >> many1(digit) -> Requires digits after dot.
    res, err = run(lexer.float, "1.")
    assert res is None  # Expects digits after dot


# --- Characters ---


def test_char_literals():
    lexer = TokenParser(empty_def)

    # Standard
    assert run(lexer.char_literal, "'a'")[0] == "a"

    # Escapes
    assert run(lexer.char_literal, "'\\n'")[0] == "\n"
    assert run(lexer.char_literal, "'\\''")[0] == "'"
    assert run(lexer.char_literal, "'\\\\'")[0] == "\\"
    assert run(lexer.char_literal, "'\\t'")[0] == "\t"

    # Unknown escape fallback ( \a -> a )
    assert run(lexer.char_literal, "'\\z'")[0] == "z"


# --- Strings ---


def test_string_literals():
    lexer = TokenParser(empty_def)

    # Standard
    assert run(lexer.string_literal, '"hello"')[0] == "hello"

    # Escapes
    assert run(lexer.string_literal, '"line\\nbreak"')[0] == "line\nbreak"
    assert run(lexer.string_literal, '"quote\\"here"')[0] == 'quote"here'

    # Empty
    assert run(lexer.string_literal, '""')[0] == ""


@given(
    st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters=['"', "\\"]))
)
def test_prop_strings(s):
    # We generate a clean string, then quote it.
    # Note: we blacklist quote and backslash to avoid manually implementing complex escaping logic in the test generator.
    # We just want to prove that "content" parses as content.

    lexer = TokenParser(empty_def)
    quoted = f'"{s}"'
    res, err = run(lexer.string_literal, quoted)

    assert res == s
    assert err is None


# --- Comments & Whitespace ---


def test_comments_integration():
    # Python style: # line comments
    lexer = TokenParser(python_style)

    # White space includes comments
    p = lexer.white_space

    # Run against a string with spaces and comments
    input_str = "   # comment\n  "
    res, err = run(p, input_str)
    assert err is None

    # Verify chaining: skip whitespace THEN parse integer
    p2 = lexer.white_space >> lexer.integer
    assert run(p2, "   # comment\n 123")[0] == 123


def test_nested_comments():
    # Haskell/Java style
    lexer = TokenParser(java_style)

    # /* /* */ */
    input_str = "/* outer /* inner */ outer */ 123"

    # Skip leading comment block before parsing integer
    p = lexer.white_space >> lexer.integer
    assert run(p, input_str)[0] == 123

    # Unclosed
    input_bad = "/* outer /* inner */ oops"
    res, err = run(lexer.integer, input_bad)
    assert res is None  # Fails to find integer


# --- Identifiers ---


def test_identifiers():
    lexer = TokenParser(python_style)

    assert run(lexer.identifier, "my_var")[0] == "my_var"
    assert run(lexer.identifier, "_private")[0] == "_private"
    assert run(lexer.identifier, "var123")[0] == "var123"

    # Reserved
    assert run(lexer.identifier, "def")[0] is None
    assert run(lexer.identifier, "class")[0] is None

    # Operators
    # '+=' is reserved in python_style, so generic operator parser should reject it
    assert run(lexer.operator, "+=")[0] is None

    # Use a non-reserved operator (made up but valid operator chars)
    assert run(lexer.operator, "-->")[0] == "-->"

    # Check reserved op matches (returns None on success)
    assert run(lexer.reserved_op("+="), "+=")[0] is None


@given(
    st.integers(min_value=1, max_value=1000),
    st.text(min_size=1, max_size=1000).filter(
        lambda s: all(c not in s for c in ["/", "/*", "*/"])
    ),
)
@settings(deadline=None)
def test_prop_nested_comments(nesting_depth, content):
    """Property test: nested comments up to 50 levels should always work."""
    lexer = TokenParser(java_style)
    open_comments = "/*" * nesting_depth
    close_comments = "*/" * nesting_depth
    input_str = f"{open_comments} {content} {close_comments} 42"
    p = lexer.white_space >> lexer.integer
    res, err = run(p, input_str)
    assert res == 42, f"Failed to parse with {nesting_depth} nesting levels"
    assert err is None


@given(
    st.lists(
        st.text(min_size=1, max_size=1000).filter(
            lambda s: all(c not in s for c in ["/", "/*", "*/"])
        ),
        min_size=1,
        max_size=1000,
    )
)
@settings(deadline=None)
def test_prop_multiple_comment_blocks(blocks):
    """Property test: multiple separate comment blocks should work."""
    lexer = TokenParser(java_style)
    # Create input with multiple comment blocks
    comment_blocks = " ".join(f"/*{block}*/" for block in blocks)
    input_str = f"{comment_blocks} 42"
    p = lexer.white_space >> lexer.integer
    res, err = run(p, input_str)
    assert res == 42
    assert err is None


@given(
    st.text(min_size=1, max_size=1000).filter(
        lambda s: all(c not in s for c in ["/", "/*", "*/"])
    ),
    st.integers(min_value=1, max_value=1000),
)
@settings(deadline=None)
def test_prop_nested_with_content(outer_content, nesting_levels):
    """Property test: nested comments with arbitrary content."""
    lexer = TokenParser(java_style)

    # Create nested structure with content at each level
    def build_nested(levels, content):
        if levels == 0:
            return content
        inner = build_nested(levels - 1, content)
        return f"/* outer {inner} outer */"

    nested_comment = build_nested(nesting_levels, outer_content)
    print(nested_comment)
    input_str = f"{nested_comment} 42"
    p = lexer.white_space >> lexer.integer
    res, err = run(p, input_str)
    assert res == 42
    assert err is None
