"""Core types and data structures for the parser combinator library.

This module defines the foundational types used throughout PyParsec:

- :class:`SourcePos` -- tracks line/column position in input
- :class:`State` -- parser state (input, position, user state)
- :class:`MessageType` / :class:`Message` / :class:`ParseError` -- error reporting
- :class:`Ok` / :class:`Error` / :class:`ParseResult` -- parse outcomes
- :class:`Parsec` -- the central parser combinator type
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, List, Optional, Sequence, Tuple, TypeVar, Union, cast

T = TypeVar("T")  # Generic type for parser results
U = TypeVar("U")  # Generic type for bind mapping
Inp = TypeVar("Inp", bound=Sequence)  # Generic type for input stream


@dataclass(frozen=True)
class SourcePos:
    """Represent a position in the input stream.

    Attributes:
        line: The 1-based line number.
        column: The 1-based column number.
        name: Optional source name (e.g. a filename).

    Example::

        >>> from pyparsec.Parsec import SourcePos
        >>> pos = SourcePos(1, 5, "test.txt")
        >>> str(pos)
        '"test.txt" (line 1, column 5)'
    """

    line: int = 1
    column: int = 1
    name: str = ""

    def __str__(self) -> str:
        """Return a human-readable ``"name" (line L, column C)`` representation."""
        name_str = f'"{self.name}" ' if self.name else ""
        return f"{name_str}(line {self.line}, column {self.column})"

    def __gt__(self, other: "SourcePos") -> bool:
        """Return ``True`` if this position is after *other*."""
        if self.line != other.line:
            return self.line > other.line
        return self.column > other.column

    def __lt__(self, other: "SourcePos") -> bool:
        """Return ``True`` if this position is before *other*."""
        if self.line != other.line:
            return self.line < other.line
        return self.column < other.column


# --- Position Update Strategies ---


def update_pos_char(pos: SourcePos, char: str) -> SourcePos:
    """Advance *pos* by a single character, handling newlines and tabs.

    Args:
        pos: The current source position.
        char: The character to advance past.

    Returns:
        A new :class:`SourcePos` with updated line and column.

    Example::

        >>> from pyparsec.Parsec import SourcePos, update_pos_char
        >>> update_pos_char(SourcePos(1, 1), 'a')
        SourcePos(line=1, column=2, name='')
        >>> update_pos_char(SourcePos(1, 1), '\\n')
        SourcePos(line=2, column=1, name='')
    """
    if char == "\n":
        return SourcePos(pos.line + 1, 1, pos.name)
    elif char == "\t":
        tab_width = 8
        new_column = pos.column + tab_width - ((pos.column - 1) % tab_width)
        return SourcePos(pos.line, new_column, pos.name)
    else:
        return SourcePos(pos.line, pos.column + 1, pos.name)


def update_pos_string(pos: SourcePos, text: str) -> SourcePos:
    """Advance *pos* by an entire string, handling newlines and tabs.

    Args:
        pos: The current source position.
        text: The string to advance past.

    Returns:
        A new :class:`SourcePos` after processing all characters in *text*.

    Example::

        >>> from pyparsec.Parsec import SourcePos, update_pos_string
        >>> update_pos_string(SourcePos(1, 1), 'hello')
        SourcePos(line=1, column=6, name='')
    """
    if not text:
        return pos
    if "\t" in text:
        new_pos = pos
        for ch in text:
            new_pos = update_pos_char(new_pos, ch)
        return new_pos

    newlines = text.count("\n")
    if newlines == 0:
        return SourcePos(pos.line, pos.column + len(text), pos.name)

    last_newline_idx = text.rfind("\n")
    new_column = len(text) - last_newline_idx
    return SourcePos(pos.line + newlines, new_column, pos.name)


def initial_pos(name: str) -> SourcePos:
    """Create a starting position (line 1, column 1) with the given source name.

    Args:
        name: The source name (e.g. a filename).

    Returns:
        A :class:`SourcePos` at line 1, column 1.

    Example::

        >>> from pyparsec.Parsec import initial_pos
        >>> initial_pos("example.txt")
        SourcePos(line=1, column=1, name='example.txt')
    """
    return SourcePos(1, 1, name)


@dataclass
class State(Generic[Inp]):
    """Parser state carrying the input stream, position, user state, and index.

    Attributes:
        input: The full input sequence (e.g. a string).
        pos: The current :class:`SourcePos` in the input.
        user: Arbitrary user-defined state threaded through parsing.
        index: The zero-based index into *input* for zero-copy parsing.

    Example::

        >>> from pyparsec.Parsec import SourcePos, State
        >>> st = State("hello", SourcePos(1, 1), None, 0)
        >>> st.remaining
        'hello'
    """

    input: Inp
    pos: SourcePos
    user: Any
    index: int = 0

    @property
    def remaining(self) -> Inp:
        """Return the unconsumed portion of the input from the current index.

        Returns:
            A slice of *input* starting at *index*.

        Example::

            >>> from pyparsec.Parsec import SourcePos, State
            >>> st = State("hello", SourcePos(1, 1), None, 2)
            >>> st.remaining
            'llo'
        """
        return cast(Inp, self.input[self.index:])


SYS_UNEXPECT = 1
UNEXPECT = 2
EXPECT = 3
MESSAGE = 4


class MessageType:
    """Categories of messages that can appear in a parse error.

    Members:
        SYS_UNEXPECT: System-generated "unexpected token" message.
        UNEXPECT: User-generated "unexpected" message (via ``not_followed_by``).
        EXPECT: "Expected" message (via ``label``).
        MESSAGE: Free-form diagnostic message (via ``fail``).
    """

    SYS_UNEXPECT = SYS_UNEXPECT
    UNEXPECT = UNEXPECT
    EXPECT = EXPECT
    MESSAGE = MESSAGE


@dataclass(frozen=True)
class Message:
    """A single diagnostic message attached to a :class:`ParseError`.

    Attributes:
        type: The :class:`MessageType` category.
        text: The human-readable message text.
    """

    type: MessageType
    text: str

    def __lt__(self, other: "Message") -> bool:
        """Compare messages by type then text for deterministic sorting."""
        if self.type != other.type:
            return self.type < other.type
        return self.text < other.text


@dataclass
class ParseError:
    """A parse error with a source position and associated diagnostic messages.

    Attributes:
        pos: The :class:`SourcePos` where the error occurred.
        messages: A list of :class:`Message` diagnostics.

    Example::

        >>> from pyparsec.Parsec import ParseError, SourcePos
        >>> err = ParseError.new_unknown(SourcePos(1, 1))
        >>> err.is_unknown()
        True
    """

    pos: SourcePos
    messages: List[Message] = field(default_factory=list)

    def __str__(self) -> str:
        """Format the error as a human-readable string with position and messages.

        Returns:
            A string like ``Parse error at (line 1, column 1): unexpected 'x'; expecting 'y'``.
        """
        if not self.messages:
            return f"Unknown parse error at {self.pos}"

        expects = sorted(list(set(m.text for m in self.messages if m.type == MessageType.EXPECT)))
        unexpects = sorted(
            list(
                set(
                    m.text
                    for m in self.messages
                    if m.type == MessageType.UNEXPECT or m.type == MessageType.SYS_UNEXPECT
                )
            )
        )
        others = sorted(list(set(m.text for m in self.messages if m.type == MessageType.MESSAGE)))

        msg_parts = []
        if unexpects:
            if len(unexpects) == 1 and unexpects[0] == "":
                msg_parts.append("unexpected end of input")
            else:
                msg_parts.append(f"unexpected {', or '.join(unexpects)}")
        if expects:
            msg_parts.append(f"expecting {', or '.join(expects)}")
        if others:
            msg_parts.extend(others)

        return f"Parse error at {self.pos}: {'; '.join(msg_parts)}"

    def is_unknown(self) -> bool:
        """Return ``True`` if this error carries no diagnostic messages.

        Returns:
            ``True`` when *messages* is empty.
        """
        return not self.messages

    def add_message(self, msg: Message) -> "ParseError":
        """Return a new :class:`ParseError` with *msg* appended (if not already present).

        Args:
            msg: The :class:`Message` to add.

        Returns:
            A new :class:`ParseError` with the message included.
        """
        if msg not in self.messages:
            return ParseError(self.pos, self.messages + [msg])
        return self

    def set_messages(self, msgs: List[Message]) -> "ParseError":
        """Return a new :class:`ParseError` with its messages replaced by *msgs*.

        Args:
            msgs: The replacement list of :class:`Message` objects.

        Returns:
            A new :class:`ParseError` with deduplicated, sorted messages.
        """
        return ParseError(self.pos, sorted(list(set(msgs))))

    @staticmethod
    def new_unknown(pos: SourcePos) -> "ParseError":
        """Create an error with no messages at the given position.

        Args:
            pos: The source position for the error.

        Returns:
            A :class:`ParseError` with an empty message list.

        Example::

            >>> from pyparsec.Parsec import ParseError, SourcePos
            >>> ParseError.new_unknown(SourcePos(1, 1)).is_unknown()
            True
        """
        return ParseError(pos, [])

    @staticmethod
    def new_message(pos: SourcePos, msg_type: MessageType, text: str) -> "ParseError":
        """Create an error with a single message at the given position.

        Args:
            pos: The source position for the error.
            msg_type: The :class:`MessageType` of the message.
            text: The message text.

        Returns:
            A :class:`ParseError` containing one :class:`Message`.

        Example::

            >>> from pyparsec.Parsec import ParseError, MessageType, SourcePos
            >>> err = ParseError.new_message(SourcePos(1, 1), MessageType.EXPECT, "'a'")
            >>> str(err)
            "Parse error at (line 1, column 1): expecting 'a'"
        """
        return ParseError(pos, [Message(msg_type, text)])

    @staticmethod
    def merge(err1: "ParseError", err2: "ParseError") -> "ParseError":
        """Merge two errors, keeping the one at the furthest position or combining messages.

        If both errors are at the same position, their messages are combined.
        Unknown errors are discarded in favour of known ones.

        Args:
            err1: The first error.
            err2: The second error.

        Returns:
            A merged :class:`ParseError`.

        Example::

            >>> from pyparsec.Parsec import ParseError, MessageType, SourcePos
            >>> e1 = ParseError.new_message(SourcePos(1, 1), MessageType.EXPECT, "'a'")
            >>> e2 = ParseError.new_message(SourcePos(1, 1), MessageType.EXPECT, "'b'")
            >>> "'a'" in str(ParseError.merge(e1, e2)) and "'b'" in str(ParseError.merge(e1, e2))
            True
        """
        if err1.is_unknown():
            return err2
        if err2.is_unknown():
            return err1

        if err1.pos > err2.pos:
            return err1
        if err2.pos > err1.pos:
            return err2

        combined_messages = sorted(list(set(err1.messages + err2.messages)))
        return ParseError(err1.pos, combined_messages)


# --- Reply Types (Algebraic Data Type) ---
@dataclass
class Ok(Generic[T]):
    """Successful parse reply carrying the result value, updated state, and any ghost errors.

    Attributes:
        value: The parsed result of type *T*.
        state: The :class:`State` after consuming input.
        error: Ghost errors from alternatives that were tried but not taken.
    """

    value: T
    state: State[Any]  # Generic over Input
    error: ParseError


@dataclass
class Error:
    """Failed parse reply carrying the error.

    Attributes:
        error: The :class:`ParseError` describing the failure.
    """

    error: ParseError


Reply = Union[Ok[T], Error]


@dataclass(frozen=True)
class ParseResult(Generic[T]):
    """The outcome of running a parser: a reply (Ok or Error) plus whether input was consumed.

    Attributes:
        reply: An :class:`Ok` or :class:`Error` reply.
        consumed: ``True`` if the parser consumed any input.

    Example::

        >>> from pyparsec.Parsec import ParseResult, ParseError, SourcePos, State
        >>> res = ParseResult.ok_consumed(42, State("x", SourcePos(), None, 1),
        ...                               ParseError.new_unknown(SourcePos()))
        >>> res.value
        42
    """

    reply: Reply[T]
    consumed: bool

    @property
    def value(self) -> Optional[T]:
        """Return the parsed value, or ``None`` if parsing failed.

        Returns:
            The result value from an :class:`Ok` reply, or ``None``.
        """
        if isinstance(self.reply, Ok):
            return self.reply.value
        return None

    @property
    def state(self) -> Optional[State]:
        """Return the post-parse state, or ``None`` if parsing failed.

        Returns:
            The :class:`State` from an :class:`Ok` reply, or ``None``.
        """
        if isinstance(self.reply, Ok):
            return self.reply.state
        return None

    @property
    def error(self) -> ParseError:
        """Return the :class:`ParseError` from the reply.

        Returns:
            The error from either an :class:`Ok` (ghost error) or :class:`Error` reply.
        """
        if isinstance(self.reply, Ok):
            return self.reply.error
        return self.reply.error

    @staticmethod
    def ok_consumed(value: T, new_state: State, err: ParseError) -> "ParseResult[T]":
        """Create a successful result that consumed input.

        Args:
            value: The parsed value.
            new_state: The state after consumption.
            err: Ghost errors from tried alternatives.

        Returns:
            A :class:`ParseResult` with ``consumed=True``.
        """
        return ParseResult(Ok(value, new_state, err), True)

    @staticmethod
    def ok_empty(value: T, original_state: State, err: ParseError) -> "ParseResult[T]":
        """Create a successful result that consumed no input.

        Args:
            value: The parsed value.
            original_state: The unchanged parser state.
            err: Ghost errors from tried alternatives.

        Returns:
            A :class:`ParseResult` with ``consumed=False``.
        """
        return ParseResult(Ok(value, original_state, err), False)

    @staticmethod
    def error_consumed(err: ParseError) -> "ParseResult[Any]":
        """Create a failed result that consumed input (cannot backtrack without ``try_parse``).

        Args:
            err: The :class:`ParseError` describing the failure.

        Returns:
            A :class:`ParseResult` with ``consumed=True``.
        """
        return ParseResult(Error(err), True)

    @staticmethod
    def error_empty(err: ParseError) -> "ParseResult[Any]":
        """Create a failed result that consumed no input (allows alternatives via ``|``).

        Args:
            err: The :class:`ParseError` describing the failure.

        Returns:
            A :class:`ParseResult` with ``consumed=False``.
        """
        return ParseResult(Error(err), False)


class Parsec(Generic[T]):
    """A parser combinator that processes input and returns a result.

    Wraps a parsing function and provides monadic combinators for composition.

    Attributes:
        parse_fn: The underlying parsing function ``State -> ParseResult[T]``.
        name: A descriptive name for debugging.

    Example::

        >>> from pyparsec import run_parser, char
        >>> val, err = run_parser(char('a'), "abc")
        >>> val
        'a'
    """

    def __init__(self, parse_fn: Callable[[State], ParseResult[T]]):
        """Create a parser from a parsing function.

        Args:
            parse_fn: A callable that takes a :class:`State` and returns a
                :class:`ParseResult`.
        """
        self.parse_fn = parse_fn

    @property
    def name(self) -> str:
        """Descriptive name for debugging."""
        return getattr(self.parse_fn, "__name__", "lambda_parser")

    def __call__(self, state: State) -> ParseResult[T]:
        """Run this parser on the given state.

        Args:
            state: The current parser :class:`State`.

        Returns:
            A :class:`ParseResult` with the outcome.
        """
        return self.parse_fn(state)

    def bind(self, f: Callable[[T], "Parsec[U]"]) -> "Parsec[U]":
        """Monadic bind: run this parser, then feed its result to *f* to get the next parser.

        Args:
            f: A function that takes the parsed value and returns a new parser.

        Returns:
            A combined :class:`Parsec` that sequences self then the parser from *f*.

        Example::

            >>> from pyparsec import run_parser, char
            >>> p = char('a').bind(lambda c: char('b').map(lambda d: c + d))
            >>> run_parser(p, "ab")[0]
            'ab'
        """

        def parse(state: State) -> ParseResult[U]:
            res_self = self(state)

            # Explicit failure check
            if isinstance(res_self.reply, Error):
                return ParseResult(res_self.reply, res_self.consumed)

            # Self succeeded
            ok_reply: Ok[T] = res_self.reply
            next_parser = f(ok_reply.value)

            res_next = next_parser(ok_reply.state)
            consumed_overall = res_self.consumed or res_next.consumed

            # Inline merge short-circuit: skip function call for no-op cases
            err1_msgs = ok_reply.error.messages
            if not err1_msgs:
                merged_err = res_next.error
            elif not res_next.error.messages:
                merged_err = ok_reply.error
            else:
                merged_err = ParseError.merge(ok_reply.error, res_next.error)

            if isinstance(res_next.reply, Error):
                return ParseResult(Error(merged_err), consumed_overall)

            # Both OK
            ok_next: Ok[U] = res_next.reply
            return ParseResult(Ok(ok_next.value, ok_next.state, merged_err), consumed_overall)

        return Parsec(parse)

    def __or__(self, other: "Parsec[U]") -> "Parsec[Union[T, U]]":
        """Try this parser first; if it fails without consuming, try *other*.

        Args:
            other: The alternative parser to try.

        Returns:
            A parser that succeeds if either ``self`` or *other* succeeds.

        Example::

            >>> from pyparsec import run_parser, char
            >>> p = char('a') | char('b')
            >>> run_parser(p, "b")[0]
            'b'
        """

        def parse(state: State) -> ParseResult[Union[T, U]]:
            res1 = self(state)

            # If Ok OR Consumed Error -> res1 wins
            if isinstance(res1.reply, Ok) or res1.consumed:
                return cast(ParseResult[Union[T, U]], res1)

            # res1 is Empty Error
            res2 = other(state)

            if not res2.consumed and isinstance(res2.reply, Error):
                # Both Empty Error -> Merge
                merged_err = ParseError.merge(res1.reply.error, res2.reply.error)
                return ParseResult.error_empty(merged_err)

            return cast(ParseResult[Union[T, U]], res2)

        return Parsec(parse)

    # --- Applicative Functor ---

    def __and__(self, other: "Parsec[U]") -> "Parsec[Tuple[T, U]]":
        """Sequence two parsers and return both results as a tuple.

        Args:
            other: The parser to run after ``self``.

        Returns:
            A parser yielding ``(self_result, other_result)``.

        Example::

            >>> from pyparsec import run_parser, char
            >>> run_parser(char('a') & char('b'), "ab")[0]
            ('a', 'b')
        """
        return self.bind(lambda val_t: other.bind(lambda val_u: _pure((val_t, val_u))))

    def __gt__(self, other: "Parsec[U]") -> "Parsec[U]":
        """Sequence two parsers, discarding the left result.

        Args:
            other: The parser whose result is kept.

        Returns:
            A parser yielding only *other*'s result.

        Example::

            >>> from pyparsec import run_parser, char
            >>> run_parser(char('a') > char('b'), "ab")[0]
            'b'
        """
        def parse(state: State) -> ParseResult[U]:
            res_self = self(state)
            if isinstance(res_self.reply, Error):
                return ParseResult(res_self.reply, res_self.consumed)
            ok_self: Ok[T] = res_self.reply
            res_other = other(ok_self.state)
            consumed = res_self.consumed or res_other.consumed
            # Inline merge short-circuit
            err1_msgs = ok_self.error.messages
            if isinstance(res_other.reply, Error):
                err2 = res_other.reply.error
                if not err1_msgs:
                    merged = err2
                elif not err2.messages:
                    merged = ok_self.error
                else:
                    merged = ParseError.merge(ok_self.error, err2)
                return ParseResult(Error(merged), consumed)
            ok_other: Ok[U] = res_other.reply
            if not err1_msgs:
                merged = ok_other.error
            elif not ok_other.error.messages:
                merged = ok_self.error
            else:
                merged = ParseError.merge(ok_self.error, ok_other.error)
            return ParseResult(Ok(ok_other.value, ok_other.state, merged), consumed)

        return Parsec(parse)

    def __lt__(self, other: "Parsec[U]") -> "Parsec[T]":
        """Sequence two parsers, discarding the right result.

        Args:
            other: The parser whose result is discarded.

        Returns:
            A parser yielding only ``self``'s result.

        Example::

            >>> from pyparsec import run_parser, char
            >>> run_parser(char('a') < char('b'), "ab")[0]
            'a'
        """
        def parse(state: State) -> ParseResult[T]:
            res_self = self(state)
            if isinstance(res_self.reply, Error):
                return ParseResult(res_self.reply, res_self.consumed)
            ok_self: Ok[T] = res_self.reply
            res_other = other(ok_self.state)
            consumed = res_self.consumed or res_other.consumed
            # Inline merge short-circuit
            err1_msgs = ok_self.error.messages
            if isinstance(res_other.reply, Error):
                err2 = res_other.reply.error
                if not err1_msgs:
                    merged = err2
                elif not err2.messages:
                    merged = ok_self.error
                else:
                    merged = ParseError.merge(ok_self.error, err2)
                return ParseResult(Error(merged), consumed)
            ok_other: Ok[U] = res_other.reply
            if not err1_msgs:
                merged = ok_other.error
            elif not ok_other.error.messages:
                merged = ok_self.error
            else:
                merged = ParseError.merge(ok_self.error, ok_other.error)
            return ParseResult(Ok(ok_self.value, ok_other.state, merged), consumed)

        return Parsec(parse)

    def __rshift__(self, other: Union["Parsec[U]", Callable[[T], "Parsec[U]"]]) -> "Parsec[U]":
        """Polymorphic sequencing / bind operator (``>>``).

        When *other* is a :class:`Parsec`, sequences self then other (discarding
        self's result). When *other* is a callable, performs monadic bind.

        Args:
            other: A parser to sequence with, or a function for bind.

        Returns:
            The sequenced or bound parser.

        Example::

            >>> from pyparsec import run_parser, char
            >>> run_parser(char('a') >> char('b'), "ab")[0]
            'b'
            >>> run_parser(char('a') >> (lambda x: char(x)), "aa")[0]
            'a'
        """
        if isinstance(other, Parsec):
            return self.__gt__(other)

        return self.bind(other)

    def label(self, msg: str) -> "Parsec[T]":
        """Attach a descriptive label to this parser for better error messages.

        If the parser fails without consuming input, the error's "expecting"
        messages are replaced with *msg*.

        Args:
            msg: The label to show in error messages (e.g. ``"identifier"``).

        Returns:
            A labelled parser.

        Example::

            >>> from pyparsec import run_parser, char
            >>> _, err = run_parser(char('a').label("the letter a"), "x")
            >>> "the letter a" in str(err)
            True
        """

        expect_msg = Message(MessageType.EXPECT, msg)

        def parse(state: State) -> ParseResult[T]:
            res = self(state)
            if res.consumed or isinstance(res.reply, Ok):
                return res
            # Empty Error — rewrite expect messages
            current_messages = res.reply.error.messages
            non_expect = [m for m in current_messages if m.type != MessageType.EXPECT]
            non_expect.append(expect_msg)
            return ParseResult(Error(ParseError(state.pos, non_expect)), False)

        return Parsec(parse)

    def map(self, f: Callable[[T], U]) -> "Parsec[U]":
        """Apply *f* to the result of this parser (functor map).

        Args:
            f: A function to transform the parsed value.

        Returns:
            A parser whose result is ``f(self_result)``.

        Example::

            >>> from pyparsec import run_parser, char
            >>> run_parser(char('a').map(str.upper), "a")[0]
            'A'
        """
        def parse(state: State) -> ParseResult[U]:
            res = self(state)
            if isinstance(res.reply, Ok):
                ok = res.reply
                return ParseResult(Ok(f(ok.value), ok.state, ok.error), res.consumed)
            return res

        return Parsec(parse)


# _pure exists to avoid a circular import with Prim.pure(); Parsec.py cannot
# import from Prim, so it keeps its own minimal "pure" for internal use.
def _pure(value: T) -> Parsec[T]:
    def parse(state: State) -> ParseResult[T]:
        return ParseResult.ok_empty(value, state, ParseError.new_unknown(state.pos))

    return Parsec(parse)
