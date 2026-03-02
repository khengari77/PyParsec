import math

import pytest
from hypothesis import given, assume, settings
from hypothesis import strategies as st

from pyparsec.Char import digit
from pyparsec.Language import empty_def, haskell_style, java_style, python_style
from pyparsec.Prim import many1, run_parser
from pyparsec.Token import TokenParser


def run(p, s):
    return run_parser(p, s)


# --- Integers ---


@given(st.integers())
def test_prop_integers(n):
    lexer = TokenParser(empty_def)
    res, err = run(lexer.integer, str(n))
    assert res == n
    assert err is None


@given(st.integers(min_value=0, max_value=0xFFFF))
def test_prop_integer_hex(n):
    """Property: hex-formatted integers parse correctly."""
    lexer = TokenParser(empty_def)
    res, err = run(lexer.integer, f"0x{n:x}")
    assert res == n
    assert err is None


@given(st.integers(min_value=0, max_value=0o7777))
def test_prop_integer_octal(n):
    """Property: octal-formatted integers parse correctly."""
    lexer = TokenParser(empty_def)
    res, err = run(lexer.integer, f"0o{n:o}")
    assert res == n
    assert err is None


@given(st.integers(min_value=0), st.sampled_from(["+", ""]))
def test_prop_integer_positive_sign(n, sign):
    """Property: positive integers work with or without + sign."""
    lexer = TokenParser(empty_def)
    res, err = run(lexer.integer, f"{sign}{n}")
    assert res == n
    assert err is None


# --- Floats ---


@given(st.floats(allow_nan=False, allow_infinity=False))
def test_prop_floats(f):
    s = str(f)
    lexer = TokenParser(empty_def)

    res, err = run(lexer.float, s)

    if err:
        pytest.fail(f"Failed to parse float {f} from string '{s}': {err}")

    assert math.isclose(res, f, rel_tol=1e-9)


@given(
    st.integers(min_value=0, max_value=999),
    st.integers(min_value=0, max_value=999),
    st.sampled_from(["", "-", "+"]),
)
def test_prop_float_decimal(whole, frac, sign):
    """Property: floats with decimal point parse correctly."""
    lexer = TokenParser(empty_def)
    s = f"{sign}{whole}.{frac}"
    res, err = run(lexer.float, s)
    assert err is None
    assert math.isclose(res, float(s), rel_tol=1e-9)


@given(
    st.integers(min_value=1, max_value=99),
    st.sampled_from(["e", "E"]),
    st.sampled_from(["", "+", "-"]),
    st.integers(min_value=0, max_value=10),
)
def test_prop_float_scientific(mantissa, e_char, e_sign, exponent):
    """Property: scientific notation floats parse correctly."""
    lexer = TokenParser(empty_def)
    s = f"{mantissa}{e_char}{e_sign}{exponent}"
    res, err = run(lexer.float, s)
    assert err is None
    assert math.isclose(res, float(s), rel_tol=1e-9)


@given(st.integers(min_value=0, max_value=999))
def test_prop_float_rejects_plain_integers(n):
    """Property: plain integers without . or e are rejected by float parser."""
    lexer = TokenParser(empty_def)
    res, err = run(lexer.float, str(n))
    assert res is None


# --- Characters ---


@given(
    st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters=["'", "\\"],
    )
)
def test_prop_char_literals(c):
    """Property: char literal parser handles arbitrary characters."""
    lexer = TokenParser(empty_def)
    res, err = run(lexer.char_literal, f"'{c}'")
    assert res == c
    assert err is None


@given(
    st.sampled_from([
        ("'\\n'", "\n"),
        ("'\\t'", "\t"),
        ("'\\''", "'"),
        ("'\\\\'", "\\"),
    ])
)
def test_prop_char_escapes(pair):
    """Property: escape sequences in char literals parse correctly."""
    lexer = TokenParser(empty_def)
    literal, expected = pair
    res, err = run(lexer.char_literal, literal)
    assert res == expected
    assert err is None


# --- Strings ---


@given(
    st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters=['"', "\\"]))
)
def test_prop_strings(s):
    lexer = TokenParser(empty_def)
    quoted = f'"{s}"'
    res, err = run(lexer.string_literal, quoted)
    assert res == s
    assert err is None


# --- Comments & Whitespace ---


@given(
    st.text(
        min_size=0,
        max_size=50,
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters=["\n", "\r"]),
    ),
    st.integers(min_value=0, max_value=999),
)
def test_prop_python_comments(comment_text, n):
    """Property: Python-style # comments are skipped before parsing."""
    lexer = TokenParser(python_style)
    p = lexer.white_space >> lexer.integer
    input_str = f"# {comment_text}\n{n}"
    res, err = run(p, input_str)
    assert res == n
    assert err is None


@given(
    st.integers(min_value=1, max_value=1000),
    st.text(min_size=1, max_size=1000).filter(
        lambda s: all(c not in s for c in ["/", "/*", "*/"])
    ),
)
@settings(deadline=None)
def test_prop_nested_comments(nesting_depth, content):
    """Property test: nested comments up to N levels should always work."""
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

    def build_nested(levels, content):
        if levels == 0:
            return content
        inner = build_nested(levels - 1, content)
        return f"/* outer {inner} outer */"

    nested_comment = build_nested(nesting_levels, outer_content)
    input_str = f"{nested_comment} 42"
    p = lexer.white_space >> lexer.integer
    res, err = run(p, input_str)
    assert res == 42
    assert err is None


# --- Identifiers ---


_python_reserved = [
    "def", "class", "if", "else", "elif", "while", "for", "return",
    "import", "from", "try", "except", "raise", "pass", "with", "as",
    "lambda", "yield", "None", "True", "False", "await", "async",
]


@given(
    st.from_regex(r"[a-zA-Z_][a-zA-Z0-9_]{0,10}", fullmatch=True).filter(
        lambda s: s not in _python_reserved
    )
)
def test_prop_identifiers(name):
    """Property: valid non-reserved identifiers are accepted."""
    lexer = TokenParser(python_style)
    res, err = run(lexer.identifier, name)
    assert res == name
    assert err is None


@given(st.sampled_from(_python_reserved))
def test_prop_reserved_rejected(name):
    """Property: reserved words are rejected by identifier parser."""
    lexer = TokenParser(python_style)
    res, err = run(lexer.identifier, name)
    assert res is None


# --- Delimiter Parsing ---


@given(st.integers(min_value=-999, max_value=999))
def test_prop_delimiters(n):
    """Property: parens, brackets, braces all parse an inner integer."""
    lexer = TokenParser(empty_def)

    # Parens
    res, err = run(lexer.parens(lexer.integer), f"({n})")
    assert res == n
    assert err is None

    # Brackets
    res, err = run(lexer.brackets(lexer.integer), f"[{n}]")
    assert res == n
    assert err is None

    # Braces
    res, err = run(lexer.braces(lexer.integer), f"{{{n}}}")
    assert res == n
    assert err is None


@given(st.integers(min_value=-999, max_value=999))
def test_prop_delimiters_with_spaces(n):
    """Property: delimiters with surrounding whitespace still parse."""
    lexer = TokenParser(empty_def)

    res, err = run(lexer.parens(lexer.integer), f"( {n} )")
    assert res == n
    assert err is None


# --- Symbol ---


@given(st.text(min_size=1, max_size=10, alphabet=st.sampled_from("abcde")))
def test_prop_symbol(s):
    """Property: symbol matches exact text and skips trailing whitespace."""
    lexer = TokenParser(empty_def)
    p = lexer.symbol(s)

    # With trailing whitespace
    res, err = run(p, s + "   ")
    assert res == s
    assert err is None

    # Exact match
    res, err = run(p, s)
    assert res == s
    assert err is None


# --- haskell_style language definition ---


@given(
    st.text(
        min_size=0,
        max_size=50,
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters=["\n", "\r", "-"]),
    ),
    st.integers(min_value=0, max_value=999),
)
def test_prop_haskell_comments(comment_text, n):
    """Property: Haskell-style comments are properly skipped."""
    lexer = TokenParser(haskell_style)
    p = lexer.white_space >> lexer.integer

    # Line comment
    res_line, err_line = run(p, f"-- {comment_text}\n{n}")
    assert res_line == n
    assert err_line is None

    # Block comment (avoid -} in content)
    safe_content = comment_text.replace("}", " ")
    res_block, err_block = run(p, f"{{- {safe_content} -}} {n}")
    assert res_block == n
    assert err_block is None


@given(
    st.text(
        min_size=0,
        max_size=30,
        alphabet=st.characters(
            blacklist_categories=("Cs",),
            blacklist_characters=["-", "{", "}"],
        ),
    ),
    st.integers(min_value=0, max_value=999),
)
def test_prop_haskell_nested_comments(content, n):
    """Property: Haskell nested block comments parse correctly."""
    lexer = TokenParser(haskell_style)
    p = lexer.white_space >> lexer.integer
    res, err = run(p, f"{{- outer {{- {content} -}} outer -}} {n}")
    assert res == n
    assert err is None
