"""Character-level parsers for matching individual characters and strings.

This module provides parsers for single characters (:func:`char`, :func:`satisfy`),
character classes (:func:`digit`, :func:`letter`, :func:`space`, etc.), and
string matching (:func:`string`, :func:`string_prime`).
"""
from collections.abc import Sequence
from typing import Callable, Optional

from .Parsec import (
    Parsec,
    update_pos_string,
)
from .Prim import (
    skip_many,
    token,
    tokens,
    tokens_prime,
)  # Assumed from prior implementation


def char(c: str) -> Parsec[str]:
    """Parse a single specific character.

    Args:
        c: The character to match.

    Returns:
        A parser that consumes and returns *c*.

    Example::

        >>> from pyparsec import run_parser, char
        >>> run_parser(char('a'), "abc")[0]
        'a'
    """
    return satisfy(lambda x: x == c).label(f"'{c}'")


def satisfy(f: Callable[[str], bool]) -> Parsec[str]:
    """Parse any character for which *f* returns ``True``.

    Args:
        f: A predicate on a single character.

    Returns:
        A parser that consumes and returns the character if *f* accepts it.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import satisfy
        >>> run_parser(satisfy(str.isupper), "Hello")[0]
        'H'
    """

    def show_char_token(char_val: str) -> str:
        return char_val if char_val != "" else "EOF"

    def test_char_token(char_val: str) -> Optional[str]:
        return char_val if f(char_val) else None

    return token(show_char_token, test_char_token)


def one_of(cs: Sequence[str]) -> Parsec[str]:
    """Parse any character that appears in *cs*.

    Args:
        cs: A sequence of acceptable characters.

    Returns:
        A parser that consumes and returns the matched character.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import one_of
        >>> run_parser(one_of("aeiou"), "echo")[0]
        'e'
    """
    return satisfy(lambda c: c in cs).label(f"one of {''.join(cs)}")


def none_of(cs: Sequence[str]) -> Parsec[str]:
    """Parse any character that does *not* appear in *cs*.

    Args:
        cs: A sequence of rejected characters.

    Returns:
        A parser that consumes and returns any character not in *cs*.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import none_of
        >>> run_parser(none_of("aeiou"), "hello")[0]
        'h'
    """
    return satisfy(lambda c: c not in cs).label(f"none of {''.join(cs)}")


def spaces() -> Parsec[None]:
    """Skip zero or more whitespace characters.

    Returns:
        A parser that consumes whitespace and returns ``None``.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Char import spaces
        >>> run_parser(spaces() > char('a'), "   a")[0]
        'a'
    """
    return skip_many(space()).label("white space")


def space() -> Parsec[str]:
    """Parse a single whitespace character.

    Returns:
        A parser that consumes and returns a whitespace character.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import space
        >>> run_parser(space(), " x")[0]
        ' '
    """
    return satisfy(str.isspace).label("space")


def newline() -> Parsec[str]:
    r"""Parse a newline character (``'\n'``).

    Returns:
        A parser that consumes and returns ``'\n'``.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import newline
        >>> run_parser(newline(), "\nabc")[0]
        '\n'
    """
    return char("\n").label("lf new-line")


def crlf() -> Parsec[str]:
    r"""Parse a carriage return followed by a newline (``'\r\n'``) and return ``'\n'``.

    Returns:
        A parser that consumes ``'\r\n'`` and returns ``'\n'``.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import crlf
        >>> run_parser(crlf(), "\r\nabc")[0]
        '\n'
    """
    return char("\r").bind(lambda _: char("\n")).label("crlf new-line")


def end_of_line() -> Parsec[str]:
    r"""Parse a line ending (either ``'\n'`` or ``'\r\n'``).

    Returns:
        A parser that consumes a line ending and returns ``'\n'``.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import end_of_line
        >>> run_parser(end_of_line(), "\n")[0]
        '\n'
    """
    return (newline() | crlf()).label("new-line")


def tab() -> Parsec[str]:
    r"""Parse a tab character (``'\t'``).

    Returns:
        A parser that consumes and returns ``'\t'``.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import tab
        >>> run_parser(tab(), "\thello")[0]
        '\t'
    """
    return char("\t").label("tab")


def upper() -> Parsec[str]:
    """Parse an uppercase letter.

    Returns:
        A parser that consumes and returns an uppercase letter.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import upper
        >>> run_parser(upper(), "Hello")[0]
        'H'
    """
    return satisfy(str.isupper).label("uppercase letter")


def lower() -> Parsec[str]:
    """Parse a lowercase letter.

    Returns:
        A parser that consumes and returns a lowercase letter.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import lower
        >>> run_parser(lower(), "hello")[0]
        'h'
    """
    return satisfy(str.islower).label("lowercase letter")


def alpha_num() -> Parsec[str]:
    """Parse an alphanumeric character.

    Returns:
        A parser that consumes and returns a letter or digit.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import alpha_num
        >>> run_parser(alpha_num(), "a1")[0]
        'a'
    """
    return satisfy(str.isalnum).label("letter or digit")


def letter() -> Parsec[str]:
    """Parse an alphabetic character.

    Returns:
        A parser that consumes and returns a letter.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import letter
        >>> run_parser(letter(), "hello")[0]
        'h'
    """
    return satisfy(str.isalpha).label("letter")


def digit() -> Parsec[str]:
    """Parse an ASCII digit.

    Returns:
        A parser that consumes and returns a digit character.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import digit
        >>> run_parser(digit(), "42")[0]
        '4'
    """
    return satisfy(str.isdigit).label("digit")


def hex_digit() -> Parsec[str]:
    """Parse a hexadecimal digit (``0-9``, ``a-f``, ``A-F``).

    Returns:
        A parser that consumes and returns a hex digit.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import hex_digit
        >>> run_parser(hex_digit(), "ff")[0]
        'f'
    """
    return satisfy(lambda c: c.isdigit() or c.lower() in "abcdef").label("hexadecimal digit")


def oct_digit() -> Parsec[str]:
    """Parse an octal digit (``0-7``).

    Returns:
        A parser that consumes and returns an octal digit.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import oct_digit
        >>> run_parser(oct_digit(), "7")[0]
        '7'
    """
    return satisfy(lambda c: c in "01234567").label("octal digit")


def any_char() -> Parsec[str]:
    """Parse any single character.

    Returns:
        A parser that consumes and returns any character.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import any_char
        >>> run_parser(any_char(), "xyz")[0]
        'x'
    """
    return satisfy(lambda _: True)


def string(s: str) -> Parsec[str]:
    """Parse an exact string.

    Consumes input atomically: if any character fails to match, the parser
    fails without consuming input.

    Args:
        s: The string to match.

    Returns:
        A parser that consumes and returns *s*.

    Example::

        >>> from pyparsec import run_parser, string
        >>> run_parser(string("hello"), "hello world")[0]
        'hello'
    """

    def show_tokens(toks: Sequence[str]) -> str:
        return f"'{''.join(toks)}'"

    return (
        tokens(show_tokens, lambda p, t: update_pos_string(p, "".join(t)), list(s))
        .map(lambda chars: "".join(chars))
        .label(f"'{s}'")
    )


def string_prime(s: str) -> Parsec[str]:
    """Parse a string without consuming input on success (lookahead).

    Like :func:`string`, but the input position is not advanced when the
    match succeeds.

    Args:
        s: The string to match.

    Returns:
        A non-consuming parser that matches *s*.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import string_prime
        >>> run_parser(string_prime("abc"), "abcdef")[0]
        'abc'
    """

    def show_tokens(toks: Sequence[str]) -> str:
        return f"'{''.join(toks)}'"

    return (
        tokens_prime(show_tokens, lambda p, t: update_pos_string(p, "".join(t)), list(s))
        .map(lambda chars: "".join(chars))
        .label(f"'{s}'")
    )
