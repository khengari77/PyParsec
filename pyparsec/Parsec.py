from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Generic, List, Optional, Sequence, Tuple, TypeVar, Union, cast

T = TypeVar("T")  # Generic type for parser results
U = TypeVar("U")  # Generic type for bind mapping
I = TypeVar("I", bound=Sequence)  # Generic type for input stream


@dataclass(frozen=True)
class SourcePos:
    """Represents a position in the input stream (Line/Column)."""

    line: int = 1
    column: int = 1
    name: str = ""

    def __str__(self) -> str:
        name_str = f'"{self.name}" ' if self.name else ""
        return f"{name_str}(line {self.line}, column {self.column})"

    def __gt__(self, other: "SourcePos") -> bool:
        if self.line != other.line:
            return self.line > other.line
        return self.column > other.column

    def __lt__(self, other: "SourcePos") -> bool:
        if self.line != other.line:
            return self.line < other.line
        return self.column < other.column


# --- Position Update Strategies ---


def update_pos_char(pos: SourcePos, char: str) -> SourcePos:
    if char == "\n":
        return SourcePos(pos.line + 1, 1, pos.name)
    elif char == "\t":
        tab_width = 8
        new_column = pos.column + tab_width - ((pos.column - 1) % tab_width)
        return SourcePos(pos.line, new_column, pos.name)
    else:
        return SourcePos(pos.line, pos.column + 1, pos.name)


def update_pos_string(pos: SourcePos, text: str) -> SourcePos:
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
    return SourcePos(1, 1, name)


@dataclass
class State(Generic[I]):
    """Parser state: input stream (Sequence), position, and user state."""

    input: I
    pos: SourcePos
    user: Any


class MessageType(Enum):
    SYS_UNEXPECT = auto()
    UNEXPECT = auto()
    EXPECT = auto()
    MESSAGE = auto()


@dataclass(frozen=True)
class Message:
    type: MessageType
    text: str

    def __lt__(self, other: "Message") -> bool:
        if self.type.value != other.type.value:
            return self.type.value < other.type.value
        return self.text < other.text


@dataclass
class ParseError:
    pos: SourcePos
    messages: List[Message] = field(default_factory=list)

    def __str__(self) -> str:
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
        return not self.messages

    def add_message(self, msg: Message) -> "ParseError":
        if msg not in self.messages:
            return ParseError(self.pos, self.messages + [msg])
        return self

    def set_messages(self, msgs: List[Message]) -> "ParseError":
        return ParseError(self.pos, sorted(list(set(msgs))))

    @staticmethod
    def new_unknown(pos: SourcePos) -> "ParseError":
        return ParseError(pos, [])

    @staticmethod
    def new_message(pos: SourcePos, msg_type: MessageType, text: str) -> "ParseError":
        return ParseError(pos, [Message(msg_type, text)])

    @staticmethod
    def merge(err1: "ParseError", err2: "ParseError") -> "ParseError":
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
    value: T
    state: State[Any]  # Generic over Input
    error: ParseError


@dataclass
class Error:
    error: ParseError


Reply = Union[Ok[T], Error]


@dataclass(frozen=True)
class ParseResult(Generic[T]):
    reply: Reply[T]
    consumed: bool

    @property
    def value(self) -> Optional[T]:
        if isinstance(self.reply, Ok):
            return self.reply.value
        return None

    @property
    def state(self) -> Optional[State]:
        if isinstance(self.reply, Ok):
            return self.reply.state
        return None

    @property
    def error(self) -> ParseError:
        if isinstance(self.reply, Ok):
            return self.reply.error
        return self.reply.error

    @staticmethod
    def ok_consumed(value: T, new_state: State, err: ParseError) -> "ParseResult[T]":
        return ParseResult(Ok(value, new_state, err), True)

    @staticmethod
    def ok_empty(value: T, original_state: State, err: ParseError) -> "ParseResult[T]":
        return ParseResult(Ok(value, original_state, err), False)

    @staticmethod
    def error_consumed(err: ParseError) -> "ParseResult[Any]":
        return ParseResult(Error(err), True)

    @staticmethod
    def error_empty(err: ParseError) -> "ParseResult[Any]":
        return ParseResult(Error(err), False)


class Parsec(Generic[T]):
    """A parser combinator that processes input and returns a result."""

    def __init__(self, parse_fn: Callable[[State], ParseResult[T]]):
        self.parse_fn = parse_fn
        self.name = getattr(parse_fn, "__name__", "lambda_parser")

    def __call__(self, state: State) -> ParseResult[T]:
        return self.parse_fn(state)

    def bind(self, f: Callable[[T], "Parsec[U]"]) -> "Parsec[U]":
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

            # Merge errors (ghost or actual)
            merged_err = ParseError.merge(ok_reply.error, res_next.error)

            if isinstance(res_next.reply, Error):
                return ParseResult(Error(merged_err), consumed_overall)

            # Both OK
            ok_next: Ok[U] = res_next.reply
            return ParseResult(Ok(ok_next.value, ok_next.state, merged_err), consumed_overall)

        return Parsec(parse)

    def __or__(self, other: "Parsec[U]") -> "Parsec[Union[T, U]]":
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
        return self.bind(lambda val_t: other.bind(lambda val_u: _pure((val_t, val_u))))

    def __gt__(self, other: "Parsec[U]") -> "Parsec[U]":
        return self.bind(lambda _: other)

    def __lt__(self, other: "Parsec[U]") -> "Parsec[T]":
        return self.bind(lambda val_t: other.bind(lambda _: _pure(val_t)))

    def __rshift__(self, other: Union["Parsec[U]", Callable[[T], "Parsec[U]"]]) -> "Parsec[U]":
        """
        Polymorphic Operator '>>'.

        1. Bind (>>=): If 'other' is a function.
           Passes the result of 'self' to 'other'.
           Example: char('a') >> (lambda x: char(x))

        2. Sequence (*> or >>): If 'other' is a Parsec object.
           Runs 'self', discards result, then runs 'other'.
           Example: char('a') >> char('b')
        """
        if isinstance(other, Parsec):
            # Sequence logic: self *> other
            return self.bind(lambda _: other)

        # Bind logic: self >>= other
        return self.bind(other)

    def label(self, msg: str) -> "Parsec[T]":
        def parse(state: State) -> ParseResult[T]:
            res = self(state)
            # Only update error if it is an Empty Error
            if isinstance(res.reply, Error) and not res.consumed:
                current_messages = res.reply.error.messages
                non_expect = [m for m in current_messages if m.type != MessageType.EXPECT]
                new_msgs = non_expect + [Message(MessageType.EXPECT, msg)]

                final_err = ParseError(state.pos, sorted(list(set(new_msgs))))
                return ParseResult.error_empty(final_err)
            return res

        return Parsec(parse)

    def map(self, f: Callable[[T], U]) -> "Parsec[U]":
        return self.bind(lambda x: _pure(f(x)))


def _pure(value: T) -> Parsec[T]:
    def parse(state: State) -> ParseResult[T]:
        return ParseResult.ok_empty(value, state, ParseError.new_unknown(state.pos))

    return Parsec(parse)
