from dataclasses import dataclass, field
from typing import List, Callable, Optional, Any, Union
from .Parsec import Parsec, State, ParseResult, ParseError, MessageType, Ok, Error, update_pos_char
from .Prim import try_parse, pure, fail, skip_many, many, lazy
from .Char import (
    char, string, satisfy, one_of, none_of, 
    digit, hex_digit, oct_digit, space, any_char
)
from .Combinators import (
    choice, skip_many1, between, sep_by, sep_by1, many1, 
    not_followed_by, option, option_maybe
)

@dataclass
class LanguageDef:
    """
    Defines the syntax rules for a language.
    """
    comment_start: str = ""          # e.g. "/*"
    comment_end: str = ""            # e.g. "*/"
    comment_line: str = ""           # e.g. "//"
    nested_comments: bool = True     # Allow /* /* nested */ */
    ident_start: Parsec[str] = satisfy(lambda c: c.isalpha() or c == '_')
    ident_letter: Parsec[str] = satisfy(lambda c: c.isalnum() or c == '_')
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
        self.white_space = self._make_white_space()
        
        # --- Lexeme Helper (skips trailing whitespace) ---
        self.lexeme = lambda p: p < self.white_space
        self.symbol = lambda name: self.lexeme(string(name))
        
        # --- Symbols ---
        self.parens = lambda p: between(self.symbol("("), self.symbol(")"), p)
        self.braces = lambda p: between(self.symbol("{"), self.symbol("}"), p)
        self.angles = lambda p: between(self.symbol("<"), self.symbol(">"), p)
        self.brackets = lambda p: between(self.symbol("["), self.symbol("]"), p)
        
        self.semi = self.symbol(";")
        self.comma = self.symbol(",")
        self.colon = self.symbol(":")
        self.dot = self.symbol(".")
        
        self.semi_sep = lambda p: sep_by(p, self.semi)
        self.semi_sep1 = lambda p: sep_by1(p, self.semi)
        self.comma_sep = lambda p: sep_by(p, self.comma)
        self.comma_sep1 = lambda p: sep_by1(p, self.comma)
        
        # --- Integers ---
        self.decimal = self.lexeme(many1(digit()).map(lambda ds: int("".join(ds))))
        
        self.hexadecimal = self.lexeme(
            (one_of(['x', 'X']) >> many1(hex_digit()))
            .map(lambda ds: int("".join(ds), 16))
        )
        
        self.octal = self.lexeme(
            (one_of(['o', 'O']) >> many1(oct_digit()))
            .map(lambda ds: int("".join(ds), 8))
        )
        
        self.natural = self.lexeme(choice([
            char('0') >> choice([
                self.hexadecimal,
                self.octal,
                self.decimal,
                pure(0)
            ]),
            self.decimal
        ]))
        
        self.integer = self.lexeme(
            (char('-') >> self.natural.map(lambda n: -n)) |
            (char('+') >> self.natural) |
            self.natural
        )

        # --- Floats ---
        # Logic: decimal . fraction . exponent? OR decimal . exponent
        def fraction() -> Parsec[str]:
            return char('.') >> many1(digit()).map(lambda ds: "." + "".join(ds))
        
        def exponent() -> Parsec[str]:
            return one_of(['e', 'E']) >> \
                   option("", one_of(['+', '-'])) .bind(lambda sign: \
                   self.decimal.map(lambda d: f"e{sign}{d}"))

        def float_val() -> Parsec[float]:
            return many1(digit()).bind(lambda ds:
                   choice([
                       fraction().bind(lambda f: 
                           option("", exponent()).map(lambda e: float("".join(ds) + f + e))
                       ),
                       exponent().map(lambda e: float("".join(ds) + e))
                   ]))

        self.float = self.lexeme(
            (char('-') >> float_val().map(lambda f: -f)) |
            (char('+') >> float_val()) |
            float_val()
        )

        # --- Chars & Strings ---
        # Escape codes map
        self._esc_map = {
            'n': '\n', 'r': '\r', 't': '\t', '\\': '\\', 
            '"': '"', "'": "'", 'b': '\b', 'f': '\f'
        }
        
        def escape_code() -> Parsec[str]:
            return char('\\') >> choice([
                one_of(list(self._esc_map.keys())).map(lambda c: self._esc_map[c]),
                # Could add numeric escapes here (\uXXXX etc)
                any_char() # Fallback: just return the char (e.g. \a -> a)
            ])

        def char_letter(quote: str) -> Parsec[str]:
            return satisfy(lambda c: c != quote and c != '\\')

        def string_char(quote:  str) -> Parsec[str]:
            return char_letter(quote) | escape_code()

        self.char_literal = self.lexeme(
            between(char("'"), char("'"), string_char("'"))
        )

        self.string_literal = self.lexeme(
            between(char('"'), char('"'), many(string_char('"')))
            .map(lambda chars: "".join(chars))
        )
        
        # --- Identifiers ---
        self.identifier = self.lexeme(self._make_identifier())
        self.reserved = lambda name: self.lexeme(self._make_reserved(name))
        
        # --- Operators ---
        self.operator = self.lexeme(self._make_operator())
        self.reserved_op = lambda name: self.lexeme(self._make_reserved_op(name))

    def _make_white_space(self) -> Parsec[None]:
        if not self.lang.comment_start and not self.lang.comment_line:
            return skip_many(space())
        
        parsers = [space()]

        if self.lang.comment_line:
            line_comment = try_parse(string(self.lang.comment_line)) >> \
                           skip_many(satisfy(lambda c: c != '\n'))
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
                    return res
                
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

                    if not curr_state.input:
                         return ParseResult.error_consumed(
                             ParseError.new_message(curr_state.pos, MessageType.UNEXPECT, "end of input in comment")
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

                return ParseResult.ok_consumed(None, curr_state, ParseError.new_unknown(curr_state.pos))

            block_comment = Parsec(parse_block_comment)
            parsers.append(block_comment)

        return skip_many(choice(parsers))

    def _make_identifier(self) -> Parsec[str]:
        def validate(name: str) -> Parsec[str]:
            if name in self.lang.reserved_names:
                return fail(f"unexpected reserved name {name!r}")
            return pure(name)

        ident = (self.lang.ident_start.bind(lambda c: 
                 many(self.lang.ident_letter).bind(lambda cs: 
                 pure(c + "".join(cs)))))
                 
        return ident.bind(validate)

    def _make_reserved(self, name: str) -> Parsec[None]:
        return try_parse(
            string(name) >> 
            not_followed_by(self.lang.ident_letter)
        ).label(f"reserved word '{name}'")

    def _make_operator(self) -> Parsec[str]:
        def validate(op: str) -> Parsec[str]:
            if op in self.lang.reserved_op_names:
                return fail(f"unexpected reserved op {op!r}")
            return pure(op)

        oper = (self.lang.op_start.bind(lambda c:
                many(self.lang.op_letter).bind(lambda cs:
                pure(c + "".join(cs)))))
        
        return oper.bind(validate)

    def _make_reserved_op(self, name: str) -> Parsec[None]:
        return try_parse(
            string(name) >>
            not_followed_by(self.lang.op_letter)
        ).label(f"reserved operator '{name}'")
