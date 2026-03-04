"""Lexer generator that builds token parsers from a language definition.

Use :class:`LanguageDef` to describe your language's syntax (comments,
identifiers, operators, reserved words) and pass it to :class:`TokenParser`
to get a full set of lexeme-level parsers.
"""
from dataclasses import dataclass, field
from typing import Any, List, TypeVar

from .Char import (
    any_char,
    char,
    digit,
    hex_digit,
    none_of,
    oct_digit,
    one_of,
    satisfy,
    space,
    string,
)
from .Combinators import (
    between,
    choice,
    not_followed_by,
    option,
    sep_by,
    sep_by1,
    skip_many1,
)
from .Parsec import Error, MessageType, Ok, Parsec, ParseError, ParseResult, State
from .Prim import fail, many, many1, pure, skip_many, skip_while, take_while, take_while1, try_parse

T = TypeVar("T")


@dataclass
class LanguageDef:
    """Define the syntax rules for a language's lexer.

    Attributes:
        comment_start: Opening string for block comments (e.g. ``"/*"``).
            Must be paired with *comment_end*.
        comment_end: Closing string for block comments (e.g. ``"*/"``).
        comment_line: Opening string for line comments (e.g. ``"//"``).
        nested_comments: Whether block comments can nest.
        ident_start: Parser for the first character of an identifier.
        ident_letter: Parser for subsequent characters of an identifier.
        op_start: Parser for the first character of an operator.
        op_letter: Parser for subsequent characters of an operator.
        reserved_names: List of reserved identifier names.
        reserved_op_names: List of reserved operator names.
        case_sensitive: Whether identifiers are case-sensitive.

    Example::

        >>> from pyparsec.Token import LanguageDef
        >>> lang = LanguageDef(comment_line="//")
    """

    comment_start: str = ""
    comment_end: str = ""
    comment_line: str = ""
    nested_comments: bool = True
    ident_start: Parsec[str] = satisfy(lambda c: c.isalpha() or c == "_")
    ident_letter: Parsec[str] = satisfy(lambda c: c.isalnum() or c == "_")
    op_start: Parsec[str] = one_of(list(":!#$%&*+./<=>?@\\^|-~"))
    op_letter: Parsec[str] = one_of(list(":!#$%&*+./<=>?@\\^|-~"))
    reserved_names: List[str] = field(default_factory=list)
    reserved_op_names: List[str] = field(default_factory=list)
    case_sensitive: bool = True


class TokenParser:
    """Build high-level lexeme parsers from a :class:`LanguageDef`.

    All parsers produced by this class automatically skip trailing whitespace
    (including comments as defined by the language).

    Attributes:
        lang: The :class:`LanguageDef` this token parser was built from.
        white_space: Parser that skips whitespace and comments.
        semi: Parser for a semicolon lexeme.
        comma: Parser for a comma lexeme.
        colon: Parser for a colon lexeme.
        dot: Parser for a dot lexeme.
        decimal: Parser for a decimal integer.
        hexadecimal: Parser for a hexadecimal integer (after ``0x``/``0X``).
        octal: Parser for an octal integer (after ``0o``/``0O``).
        natural: Parser for a natural number (decimal, hex, or octal).
        integer: Parser for a signed or unsigned integer.
        float: Parser for a floating-point number.
        char_literal: Parser for a single-quoted character literal.
        string_literal: Parser for a double-quoted string literal.
        identifier: Parser for a non-reserved identifier.
        operator: Parser for a non-reserved operator.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Token import LanguageDef, TokenParser
        >>> tp = TokenParser(LanguageDef())
        >>> run_parser(tp.integer, "42")[0]
        42
    """

    def __init__(self, lang: LanguageDef):
        """Create a token parser from the given language definition.

        Args:
            lang: The :class:`LanguageDef` describing the language syntax.

        Raises:
            ValueError: If only one of *comment_start*/*comment_end* is set.
        """
        if bool(lang.comment_start) != bool(lang.comment_end):
            raise ValueError(
                "LanguageDef: comment_start and comment_end must both be set or both be empty. "
                f"Got comment_start={lang.comment_start!r}, comment_end={lang.comment_end!r}"
            )

        self.lang = lang

        # --- Whitespace & Comments ---
        self.white_space: Parsec[None] = self._make_white_space()

        # --- Symbols ---
        self.semi: Parsec[str] = self.symbol(";")
        self.comma: Parsec[str] = self.symbol(",")
        self.colon: Parsec[str] = self.symbol(":")
        self.dot: Parsec[str] = self.symbol(".")

        # --- Integers ---
        self.decimal: Parsec[int] = self.lexeme(take_while1(str.isdigit).map(int))

        self.hexadecimal: Parsec[int] = self.lexeme(
            (one_of(["x", "X"]) >> take_while1(lambda c: c in "0123456789abcdefABCDEF")).map(
                lambda s: int(s, 16)
            )
        )

        self.octal: Parsec[int] = self.lexeme(
            (one_of(["o", "O"]) >> take_while1(lambda c: c in "01234567")).map(
                lambda s: int(s, 8)
            )
        )

        self.natural: Parsec[int] = self.lexeme(
            choice(
                [
                    char("0") >> choice([self.hexadecimal, self.octal, self.decimal, pure(0)]),
                    self.decimal,
                ]
            )
        )

        self.integer: Parsec[int] = self.lexeme(
            (char("-") >> self.natural.map(lambda n: -n))
            | (char("+") >> self.natural)
            | self.natural
        )

        # --- Floats ---
        def fraction() -> Parsec[str]:
            return char(".") >> take_while1(str.isdigit).map(lambda ds: "." + ds)

        def exponent() -> Parsec[str]:
            return one_of(["e", "E"]) >> option("", one_of(["+", "-"])).bind(
                lambda sign: self.decimal.map(lambda d: f"e{sign}{d}")
            )

        def float_val() -> Parsec[float]:
            return take_while1(str.isdigit).bind(
                lambda ds: choice(
                    [
                        fraction().bind(
                            lambda f: option("", exponent()).map(
                                lambda e: float(ds + f + e)
                            )
                        ),
                        exponent().map(lambda e: float(ds + e)),
                    ]
                )
            )

        self.float: Parsec[float] = self.lexeme(
            (char("-") >> float_val().map(lambda f: -f)) | (char("+") >> float_val()) | float_val()
        )

        # --- Chars & Strings ---
        self._esc_map = {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "\\": "\\",
            '"': '"',
            "'": "'",
            "b": "\b",
            "f": "\f",
        }

        def escape_code() -> Parsec[str]:
            return char("\\") >> choice(
                [one_of(list(self._esc_map.keys())).map(lambda c: self._esc_map[c]), any_char()]
            )

        def char_letter(quote: str) -> Parsec[str]:
            return satisfy(lambda c: c != quote and c != "\\")

        def string_char(quote: str) -> Parsec[str]:
            return char_letter(quote) | escape_code()

        self.char_literal: Parsec[str] = self.lexeme(
            between(char("'"), char("'"), string_char("'"))
        )

        def _bulk_string(quote: str) -> Parsec[str]:
            """Parse a string literal using bulk scanning for non-special chars."""
            chunk = take_while(lambda c: c != quote and c != "\\")

            def _string_body_loop(state: State) -> ParseResult[str]:
                parts: list[str] = []
                current_state = state
                consumed_any = False

                while True:
                    # Bulk scan non-special characters
                    chunk_res = chunk(current_state)
                    if isinstance(chunk_res.reply, Ok) and chunk_res.consumed:
                        parts.append(chunk_res.reply.value)
                        current_state = chunk_res.reply.state
                        consumed_any = True

                    # Try escape sequence
                    esc_res = escape_code()(current_state)
                    if isinstance(esc_res.reply, Ok) and esc_res.consumed:
                        parts.append(esc_res.reply.value)
                        current_state = esc_res.reply.state
                        consumed_any = True
                        continue

                    # Neither chunk nor escape matched — we're done
                    break

                result = "".join(parts)
                if consumed_any:
                    return ParseResult.ok_consumed(
                        result, current_state, ParseError.new_unknown(current_state.pos)
                    )
                return ParseResult.ok_empty(
                    result, current_state, ParseError.new_unknown(current_state.pos)
                )

            return between(char(quote), char(quote), Parsec(_string_body_loop))

        self.string_literal: Parsec[str] = self.lexeme(_bulk_string('"'))

        # --- Identifiers ---
        self.identifier: Parsec[str] = self.lexeme(self._make_identifier())

        # --- Operators ---
        self.operator: Parsec[str] = self.lexeme(self._make_operator())

    # --- Methods (Previously Lambdas) ---

    def lexeme(self, p: Parsec[T]) -> Parsec[T]:
        """Parse *p* then skip trailing whitespace and comments.

        Args:
            p: The parser whose result is kept.

        Returns:
            A parser that yields *p*'s result after consuming trailing whitespace.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> from pyparsec.Char import digit
            >>> run_parser(tp.lexeme(digit()), "5  ")[0]
            '5'
        """
        return p < self.white_space

    def symbol(self, name: str) -> Parsec[str]:
        """Parse the string *name* then skip trailing whitespace.

        Args:
            name: The exact string to match.

        Returns:
            A lexeme parser that yields *name*.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> run_parser(tp.symbol("+"), "+  ")[0]
            '+'
        """
        return self.lexeme(string(name))

    def parens(self, p: Parsec[T]) -> Parsec[T]:
        """Parse *p* enclosed in parentheses ``(`` ... ``)``.

        Args:
            p: The content parser.

        Returns:
            A parser yielding *p*'s result.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> run_parser(tp.parens(tp.integer), "(42)")[0]
            42
        """
        return between(self.symbol("("), self.symbol(")"), p)

    def braces(self, p: Parsec[T]) -> Parsec[T]:
        """Parse *p* enclosed in curly braces ``{`` ... ``}``.

        Args:
            p: The content parser.

        Returns:
            A parser yielding *p*'s result.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> run_parser(tp.braces(tp.integer), "{42}")[0]
            42
        """
        return between(self.symbol("{"), self.symbol("}"), p)

    def angles(self, p: Parsec[T]) -> Parsec[T]:
        """Parse *p* enclosed in angle brackets ``<`` ... ``>``.

        Args:
            p: The content parser.

        Returns:
            A parser yielding *p*'s result.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> run_parser(tp.angles(tp.integer), "<42>")[0]
            42
        """
        return between(self.symbol("<"), self.symbol(">"), p)

    def brackets(self, p: Parsec[T]) -> Parsec[T]:
        """Parse *p* enclosed in square brackets ``[`` ... ``]``.

        Args:
            p: The content parser.

        Returns:
            A parser yielding *p*'s result.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> run_parser(tp.brackets(tp.integer), "[42]")[0]
            42
        """
        return between(self.symbol("["), self.symbol("]"), p)

    def semi_sep(self, p: Parsec[T]) -> Parsec[List[T]]:
        """Parse zero or more occurrences of *p* separated by semicolons.

        Args:
            p: The element parser.

        Returns:
            A parser yielding a (possibly empty) list.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> run_parser(tp.semi_sep(tp.integer), "1;2;3")[0]
            [1, 2, 3]
        """
        return sep_by(p, self.semi)

    def semi_sep1(self, p: Parsec[T]) -> Parsec[List[T]]:
        """Parse one or more occurrences of *p* separated by semicolons.

        Args:
            p: The element parser.

        Returns:
            A parser yielding a non-empty list.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> run_parser(tp.semi_sep1(tp.integer), "1;2")[0]
            [1, 2]
        """
        return sep_by1(p, self.semi)

    def comma_sep(self, p: Parsec[T]) -> Parsec[List[T]]:
        """Parse zero or more occurrences of *p* separated by commas.

        Args:
            p: The element parser.

        Returns:
            A parser yielding a (possibly empty) list.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> run_parser(tp.comma_sep(tp.integer), "1,2,3")[0]
            [1, 2, 3]
        """
        return sep_by(p, self.comma)

    def comma_sep1(self, p: Parsec[T]) -> Parsec[List[T]]:
        """Parse one or more occurrences of *p* separated by commas.

        Args:
            p: The element parser.

        Returns:
            A parser yielding a non-empty list.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Token import LanguageDef, TokenParser
            >>> tp = TokenParser(LanguageDef())
            >>> run_parser(tp.comma_sep1(tp.integer), "1,2")[0]
            [1, 2]
        """
        return sep_by1(p, self.comma)

    def reserved(self, name: str) -> Parsec[None]:
        """Parse a reserved word, ensuring it is not a prefix of a longer identifier.

        Args:
            name: The reserved word to match.

        Returns:
            A lexeme parser that yields ``None``.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Language import haskell
            >>> run_parser(haskell.reserved("let"), "let ")[0] is None
            True
        """
        return self.lexeme(self._make_reserved(name))

    def reserved_op(self, name: str) -> Parsec[None]:
        """Parse a reserved operator, ensuring it is not a prefix of a longer operator.

        Args:
            name: The reserved operator to match.

        Returns:
            A lexeme parser that yields ``None``.

        Example::

            >>> from pyparsec import run_parser
            >>> from pyparsec.Language import haskell
            >>> run_parser(haskell.reserved_op("="), "= ")[0] is None
            True
        """
        return self.lexeme(self._make_reserved_op(name))

    # --- Internal Builders ---

    def _make_white_space(self) -> Parsec[None]:
        if not self.lang.comment_start and not self.lang.comment_line:
            return skip_while(str.isspace)

        from .Prim import skip_while1

        # Fix: Annotate list to handle Parsec[str] and Parsec[None] variance issue
        parsers: List[Parsec[Any]] = [skip_while1(str.isspace)]

        if self.lang.comment_line:
            line_comment = try_parse(string(self.lang.comment_line)) >> skip_many(
                satisfy(lambda c: c != "\n")
            )
            parsers.append(line_comment)

        if self.lang.comment_start and self.lang.comment_end:
            start_p = try_parse(string(self.lang.comment_start))
            end_p = try_parse(string(self.lang.comment_end))
            marker_chars = list(set(self.lang.comment_start[:1] + self.lang.comment_end[:1]))

            scan_non_markers = skip_many1(none_of(marker_chars))
            scan_one_marker = one_of(marker_chars)

            def parse_block_comment(state: State) -> ParseResult[None]:
                res = start_p(state)
                if isinstance(res.reply, Error):
                    # Fix: Ensure Return type matches ParseResult[None]
                    return ParseResult(Error(res.reply.error), res.consumed)

                curr_state = res.reply.state
                nesting = 1

                while nesting > 0:
                    res_end = end_p(curr_state)
                    if isinstance(res_end.reply, Ok):
                        nesting -= 1
                        curr_state = res_end.reply.state
                        continue

                    if self.lang.nested_comments:
                        res_start = start_p(curr_state)
                        if isinstance(res_start.reply, Ok):
                            nesting += 1
                            curr_state = res_start.reply.state
                            continue

                    if curr_state.index >= len(curr_state.input):
                        return ParseResult.error_consumed(
                            ParseError.new_message(
                                curr_state.pos, MessageType.UNEXPECT, "end of input in comment"
                            )
                        )

                    res_skip = scan_non_markers(curr_state)
                    if isinstance(res_skip.reply, Ok):
                        curr_state = res_skip.reply.state
                        continue

                    res_mk = scan_one_marker(curr_state)
                    if isinstance(res_mk.reply, Ok):
                        curr_state = res_mk.reply.state
                        continue

                    return ParseResult.error_consumed(ParseError.new_unknown(curr_state.pos))

                return ParseResult.ok_consumed(
                    None, curr_state, ParseError.new_unknown(curr_state.pos)
                )

            block_comment = Parsec(parse_block_comment)
            parsers.append(block_comment)

        return skip_many(choice(parsers))

    def _make_identifier(self) -> Parsec[str]:
        def validate(name: str) -> Parsec[str]:
            if name in self.lang.reserved_names:
                return fail(f"unexpected reserved name {name!r}")
            return pure(name)

        ident = self.lang.ident_start.bind(
            lambda c: many(self.lang.ident_letter).bind(lambda cs: pure(c + "".join(cs)))
        )

        return ident.bind(validate)

    def _make_reserved(self, name: str) -> Parsec[None]:
        return try_parse(string(name) >> not_followed_by(self.lang.ident_letter)).label(
            f"reserved word '{name}'"
        )

    def _make_operator(self) -> Parsec[str]:
        def validate(op: str) -> Parsec[str]:
            if op in self.lang.reserved_op_names:
                return fail(f"unexpected reserved op {op!r}")
            return pure(op)

        oper = self.lang.op_start.bind(
            lambda c: many(self.lang.op_letter).bind(lambda cs: pure(c + "".join(cs)))
        )

        return oper.bind(validate)

    def _make_reserved_op(self, name: str) -> Parsec[None]:
        return try_parse(string(name) >> not_followed_by(self.lang.op_letter)).label(
            f"reserved operator '{name}'"
        )
