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
from .Prim import fail, many, many1, pure, skip_many, try_parse

T = TypeVar("T")


@dataclass
class LanguageDef:
    """
    Defines the syntax rules for a language.
    """

    comment_start: str = ""  # e.g. "/*"
    comment_end: str = ""  # e.g. "*/"
    comment_line: str = ""  # e.g. "//"
    nested_comments: bool = True  # Allow /* /* nested */ */
    ident_start: Parsec[str] = satisfy(lambda c: c.isalpha() or c == "_")
    ident_letter: Parsec[str] = satisfy(lambda c: c.isalnum() or c == "_")
    op_start: Parsec[str] = one_of(list(":!#$%&*+./<=>?@\\^|-~"))
    op_letter: Parsec[str] = one_of(list(":!#$%&*+./<=>?@\\^|-~"))
    reserved_names: List[str] = field(default_factory=list)
    reserved_op_names: List[str] = field(default_factory=list)
    case_sensitive: bool = True


class TokenParser:
    """
    A helper that generates high-level parsers (lexemes) for a specific LanguageDef.
    """

    def __init__(self, lang: LanguageDef):
        self.lang = lang

        # --- Whitespace & Comments ---
        self.white_space: Parsec[None] = self._make_white_space()

        # --- Symbols ---
        self.semi: Parsec[str] = self.symbol(";")
        self.comma: Parsec[str] = self.symbol(",")
        self.colon: Parsec[str] = self.symbol(":")
        self.dot: Parsec[str] = self.symbol(".")

        # --- Integers ---
        self.decimal: Parsec[int] = self.lexeme(many1(digit()).map(lambda ds: int("".join(ds))))

        self.hexadecimal: Parsec[int] = self.lexeme(
            (one_of(["x", "X"]) >> many1(hex_digit())).map(lambda ds: int("".join(ds), 16))
        )

        self.octal: Parsec[int] = self.lexeme(
            (one_of(["o", "O"]) >> many1(oct_digit())).map(lambda ds: int("".join(ds), 8))
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
            return char(".") >> many1(digit()).map(lambda ds: "." + "".join(ds))

        def exponent() -> Parsec[str]:
            return one_of(["e", "E"]) >> option("", one_of(["+", "-"])).bind(
                lambda sign: self.decimal.map(lambda d: f"e{sign}{d}")
            )

        def float_val() -> Parsec[float]:
            return many1(digit()).bind(
                lambda ds: choice(
                    [
                        fraction().bind(
                            lambda f: option("", exponent()).map(
                                lambda e: float("".join(ds) + f + e)
                            )
                        ),
                        exponent().map(lambda e: float("".join(ds) + e)),
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

        self.string_literal: Parsec[str] = self.lexeme(
            between(char('"'), char('"'), many(string_char('"'))).map(lambda chars: "".join(chars))
        )

        # --- Identifiers ---
        self.identifier: Parsec[str] = self.lexeme(self._make_identifier())

        # --- Operators ---
        self.operator: Parsec[str] = self.lexeme(self._make_operator())

    # --- Methods (Previously Lambdas) ---

    def lexeme(self, p: Parsec[T]) -> Parsec[T]:
        """Parses p, then skips trailing whitespace."""
        return p < self.white_space

    def symbol(self, name: str) -> Parsec[str]:
        """Parses a string symbol, then skips trailing whitespace."""
        return self.lexeme(string(name))

    def parens(self, p: Parsec[T]) -> Parsec[T]:
        return between(self.symbol("("), self.symbol(")"), p)

    def braces(self, p: Parsec[T]) -> Parsec[T]:
        return between(self.symbol("{"), self.symbol("}"), p)

    def angles(self, p: Parsec[T]) -> Parsec[T]:
        return between(self.symbol("<"), self.symbol(">"), p)

    def brackets(self, p: Parsec[T]) -> Parsec[T]:
        return between(self.symbol("["), self.symbol("]"), p)

    def semi_sep(self, p: Parsec[T]) -> Parsec[List[T]]:
        return sep_by(p, self.semi)

    def semi_sep1(self, p: Parsec[T]) -> Parsec[List[T]]:
        return sep_by1(p, self.semi)

    def comma_sep(self, p: Parsec[T]) -> Parsec[List[T]]:
        return sep_by(p, self.comma)

    def comma_sep1(self, p: Parsec[T]) -> Parsec[List[T]]:
        return sep_by1(p, self.comma)

    def reserved(self, name: str) -> Parsec[None]:
        return self.lexeme(self._make_reserved(name))

    def reserved_op(self, name: str) -> Parsec[None]:
        return self.lexeme(self._make_reserved_op(name))

    # --- Internal Builders ---

    def _make_white_space(self) -> Parsec[None]:
        if not self.lang.comment_start and not self.lang.comment_line:
            return skip_many(space())

        # Fix: Annotate list to handle Parsec[str] and Parsec[None] variance issue
        parsers: List[Parsec[Any]] = [space()]

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
