from typing import Callable, List, Optional, Sequence

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


# Helper function: Parses a single character
def char(c: str) -> Parsec[str]:
    """Parses a single character c and returns it."""
    return satisfy(lambda x: x == c).label(f"'{c}'")


# Core function: Succeeds if the character satisfies a predicate
def satisfy(f: Callable[[str], bool]) -> Parsec[str]:
    """Succeeds for any character where f returns True. Returns the parsed character."""

    def show_char_token(char_val: str) -> str:
        return char_val if char_val != "" else "EOF"

    def test_char_token(char_val: str) -> Optional[str]:
        return char_val if f(char_val) else None

    return token(show_char_token, test_char_token)


# 1. oneOf: Parses any character in the provided list
def one_of(cs: List[str]) -> Parsec[str]:
    """Succeeds if the current character is in cs. Returns the parsed character."""
    return satisfy(lambda c: c in cs).label(f"one of {''.join(cs)}")


# 2. noneOf: Parses any character not in the provided list
def none_of(cs: List[str]) -> Parsec[str]:
    """Succeeds if the current character is not in cs. Returns the parsed character."""
    return satisfy(lambda c: c not in cs).label(f"none of {''.join(cs)}")


# 3. spaces: Skips zero or more whitespace characters
def spaces() -> Parsec[None]:
    """Skips zero or more whitespace characters."""
    return skip_many(space()).label("white space")


# 4. space: Parses a whitespace character
def space() -> Parsec[str]:
    """Parses a whitespace character and returns it."""
    return satisfy(str.isspace).label("space")


# 5. newline: Parses a newline character
def newline() -> Parsec[str]:
    """Parses a newline character ('\\n') and returns it."""
    return char("\n").label("lf new-line")


# 6. crlf: Parses a carriage return followed by a newline
def crlf() -> Parsec[str]:
    """Parses '\\r\\n' and returns '\\n'."""
    return char("\r").bind(lambda _: char("\n")).label("crlf new-line")


# 7. endOfLine: Parses either a newline or a crlf
def end_of_line() -> Parsec[str]:
    return (newline() | crlf()).label("new-line")


# 8. tab: Parses a tab character
def tab() -> Parsec[str]:
    """Parses a tab character ('\\t') and returns it."""
    return char("\t").label("tab")


# 9. upper: Parses an uppercase letter
def upper() -> Parsec[str]:
    """Parses an uppercase letter and returns it."""
    return satisfy(str.isupper).label("uppercase letter")


# 10. lower: Parses a lowercase letter
def lower() -> Parsec[str]:
    """Parses a lowercase letter and returns it."""
    return satisfy(str.islower).label("lowercase letter")


# 11. alphaNum: Parses an alphanumeric character
def alpha_num() -> Parsec[str]:
    """Parses an alphabetic or numeric character and returns it."""
    return satisfy(str.isalnum).label("letter or digit")


# 12. letter: Parses an alphabetic character
def letter() -> Parsec[str]:
    """Parses an alphabetic character and returns it."""
    return satisfy(str.isalpha).label("letter")


# 13. digit: Parses an ASCII digit
def digit() -> Parsec[str]:
    """Parses an ASCII digit and returns it."""
    return satisfy(str.isdigit).label("digit")


# 14. hexDigit: Parses a hexadecimal digit
def hex_digit() -> Parsec[str]:
    """Parses a hexadecimal digit (0-9, a-f, A-F) and returns it."""
    return satisfy(lambda c: c.isdigit() or c.lower() in "abcdef").label("hexadecimal digit")


# 15. octDigit: Parses an octal digit
def oct_digit() -> Parsec[str]:
    """Parses an octal digit (0-7) and returns it."""
    return satisfy(lambda c: c in "01234567").label("octal digit")


# 16. anyChar: Parses any character
def any_char() -> Parsec[str]:
    """Parses any character and returns it."""
    return satisfy(lambda _: True)


# 17. string: Parses a specific string
def string(s: str) -> Parsec[str]:
    """Parses the exact string s and returns it."""

    def show_tokens(toks: Sequence[str]) -> str:
        return f"'{''.join(toks)}'"

    return (
        tokens(show_tokens, lambda p, t: update_pos_string(p, "".join(t)), list(s))
        .map(lambda chars: "".join(chars))
        .label(f"'{s}'")
    )


# 18. string': Parses a string without consuming input on success
def string_prime(s: str) -> Parsec[str]:
    """Parses the string s without consuming input on success."""

    def show_tokens(toks: Sequence[str]) -> str:
        return f"'{''.join(toks)}'"

    return (
        tokens_prime(show_tokens, lambda p, t: update_pos_string(p, "".join(t)), list(s))
        .map(lambda chars: "".join(chars))
        .label(f"'{s}'")
    )
