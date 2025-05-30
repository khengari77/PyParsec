from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Tuple, List, TypeVar, Generic
from enum import Enum, auto

T = TypeVar('T')  # Generic type for parser results
U = TypeVar('U')

@dataclass
class SourcePos:
    """Represents the current position in the input stream."""
    line: int = 1
    column: int = 1
    name: str = ""

# pyparsec/Parsec.py
    def update(self, token: str) -> 'SourcePos':
        """
        Update position based on a token (e.g., character).
        Handles newlines and tabs correctly.
        """
        if token == '\n':
            return SourcePos(self.line + 1, 1, self.name)
        elif token == '\t':
            # Advance to the next tab stop (assuming tab stops are every 8 columns)
            # Correct logic: new_col = old_col + tab_width - (old_col - 1) % tab_width
            tab_width = 8
            new_column = self.column + tab_width - ((self.column - 1) % tab_width)
            return SourcePos(self.line, new_column, self.name)
        else:
            # For any other character, increment the column by 1
            return SourcePos(self.line, self.column + 1, self.name)
    def __str__(self) -> str:
        return f"{self.name} line {self.line}, column {self.column}"

    def __gt__(self, other: 'SourcePos') -> bool:
        if self.line != other.line:
            return self.line > other.line
        return self.column > other.column

    def __lt__(self, other: 'SourcePos') -> bool:
        if self.line != other.line:
            return self.line < other.line
        return self.column < other.column

    def __eq__(self, other: 'SourcePos') -> bool:
        return self.line == other.line and self.column == other.column

@dataclass
class State(Generic[T]):
    """Parser state: input stream, position, and user state."""
    input: str  # Simplified to string input; could be generalized
    pos: SourcePos
    user: Any


class MessageType(Enum):
    SYS_UNEXPECT = auto()  # System-generated unexpected token (e.g., from satisfy)
    UNEXPECT = auto()      # User-generated unexpected token (e.g., from unexpected())
    EXPECT = auto()        # Expected item (e.g., from label() or <?>)
    MESSAGE = auto()       # Raw message (e.g., from fail())

@dataclass
class Message:
    type: MessageType
    text: str

    # For sorting and merging (Parsec orders them)
    def __lt__(self, other: 'Message') -> bool:
        if self.type.value != other.type.value:
            return self.type.value < other.type.value
        return self.text < other.text # Arbitrary but consistent tie-break

    # __eq__ and __hash__ will be auto-generated by dataclass if not provided,
    # but good to be explicit if we add custom __lt__
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Message):
            return NotImplemented
        return self.type == other.type and self.text == other.text

    def __hash__(self) -> int:
        return hash((self.type, self.text))

@dataclass
class ParseError:
    """Represents a parsing error with a position and list of messages."""
    pos: SourcePos
    messages: List[Message] = field(default_factory=list) # Now a list of Message objects

    def __str__(self) -> str:
        if not self.messages:
            return f"Unknown parse error at {self.pos}"

        # Simplified formatting for now, can be made richer like Haskell's showErrorMessages
        # Group messages by type for better output (optional, but good for complex errors)
        expects = sorted(list(set(m.text for m in self.messages if m.type == MessageType.EXPECT)))
        unexpects = sorted(list(set(m.text for m in self.messages if m.type == MessageType.UNEXPECT or m.type == MessageType.SYS_UNEXPECT)))
        others = sorted(list(set(m.text for m in self.messages if m.type == MessageType.MESSAGE)))

        msg_parts = []
        if unexpects:
            if len(unexpects) == 1 and unexpects[0] == "": # For SysUnExpect "" (EOF)
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

    def add_message(self, msg: Message) -> 'ParseError':
        # Avoid duplicate messages of the same type and text
        if msg not in self.messages:
            return ParseError(self.pos, self.messages + [msg])
        return self

    def set_messages(self, msgs: List[Message]) -> 'ParseError':
        return ParseError(self.pos, sorted(list(set(msgs)))) # Keep them sorted and unique

    @staticmethod
    def new_unknown(pos: SourcePos) -> 'ParseError':
        return ParseError(pos, [])

    @staticmethod
    def new_message(pos: SourcePos, msg_type: MessageType, text: str) -> 'ParseError':
        return ParseError(pos, [Message(msg_type, text)])

    # Key function for merging errors
    @staticmethod
    def merge(err1: 'ParseError', err2: 'ParseError') -> 'ParseError':
        # If one is unknown, prefer the other
        if err1.is_unknown(): return err2
        if err2.is_unknown(): return err1

        # Compare positions
        if err1.pos > err2.pos: return err1
        if err2.pos > err1.pos: return err2

        # Positions are the same, merge messages
        # Using set to keep messages unique, then converting back to list and sorting
        # Sorting helps in consistent error messages and follows Parsec's behavior.
        combined_messages = sorted(list(set(err1.messages + err2.messages)))
        return ParseError(err1.pos, combined_messages)

@dataclass
class Reply(Generic[T]):
    value: Optional[T]
    state: State # The state *after* this part of the parse attempt
    error: Optional[ParseError]
    # is_ok: bool # Could be implicit: value is not None and (error is None or error.is_unknown())

# ParseResult of a parser function, now explicitly stating consumption
@dataclass
class ParseResult(Generic[T]):
    reply: Reply[T]
    consumed: bool # True if input was consumed, False otherwise

    @property
    def value(self) -> Optional[T]:
        return self.reply.value

    @property
    def state(self) -> State:
        return self.reply.state

    @property
    def error(self) -> Optional[ParseError]:
        return self.reply.error

    @staticmethod
    def ok_consumed(value: T, new_state: State, err: Optional[ParseError]) -> 'ParseResult[T]':
        return ParseResult(Reply(value, new_state, err), True)

    @staticmethod
    def ok_empty(value: T, original_state: State, err: Optional[ParseError]) -> 'ParseResult[T]':
        # For ok_empty, the state in Reply should be the original_state
        # if we strictly follow Parsec, though often new_state is passed if value depends on it.
        # Let's keep it simple: state reflects the state *after* this logical step.
        return ParseResult(Reply(value, original_state, err), False)

    @staticmethod
    def error_consumed(new_state: State, err: ParseError) -> 'ParseResult[Any]': # Use Any for error results
        return ParseResult(Reply(None, new_state, err), True)

    @staticmethod
    def error_empty(original_state: State, err: ParseError) -> 'ParseResult[Any]':
        return ParseResult(Reply(None, original_state, err), False)

class Parsec(Generic[T]):
    """A parser combinator that processes input and returns a result."""
    def __init__(self, parse_fn: Callable[[State], ParseResult[T]]): # Input function produces ParseResult[T]
        self.parse_fn = parse_fn
        self.name = parse_fn.__name__

    def __call__(self, state: State) -> ParseResult[T]: # Parsec[T] produces ParseResult[T]
        return self.parse_fn(state)

    # Monadic bind (>>=)
    # In Parsec.py, class Parsec:
    def bind(self, f: Callable[[T], 'Parsec[U]']) -> 'Parsec[U]':
        def parse(state: State) -> ParseResult[U]:
            res_self = self(state) # res_self is ParseResult[T]

            # If self failed with a "known" error, propagate it.
            if res_self.error and not res_self.error.is_unknown():
                return ParseResult(res_self.reply, res_self.consumed)

            # Otherwise, self succeeded (its error is unknown or None).
            # The value res_self.value (which can be None) is passed to f.
            next_parser = f(res_self.value)
            # Run next_parser on the state *after* self has processed
            res_next = next_parser(res_self.state)

            consumed_overall = res_self.consumed or res_next.consumed

            if res_next.error and not res_next.error.is_unknown():
                # next_parser failed with a known error. Merge errors.
                final_err = ParseError.merge(
                    res_self.error or ParseError.new_unknown(res_self.state.pos), # error from self (likely unknown)
                    res_next.error
                )
                # The reply uses res_next.state because that's where next_parser failed.
                return ParseResult(Reply(None, res_next.state, final_err), consumed_overall)

            # Both self and next_parser succeeded (or had unknown errors).
            final_err_on_success = ParseError.merge(
                res_self.error or ParseError.new_unknown(res_self.state.pos),
                res_next.error or ParseError.new_unknown(res_next.state.pos)
            )
            return ParseResult(Reply(res_next.value, res_next.state, final_err_on_success), consumed_overall)
        return Parsec(parse)

    # Alternative (<|>)
    def __or__(self, other: 'Parsec[T]') -> 'Parsec[T]':
        def parse(state: State) -> ParseResult[T]:
            res1 = self(state)
    
            # If res1 succeeded (error is unknown/None), or if res1 consumed input (even if it failed),
            # then res1's result is final for this choice.
            if (res1.error is None or res1.error.is_unknown()) or res1.consumed:
                return res1
    
            # At this point, res1 is an "empty error" (failed without consuming, error is known).
            # Try the 'other' parser.
            res2 = other(state)
    
            # If res2 also resulted in an "empty error", then merge the errors from res1 and res2.
            if not res2.consumed and (res2.error and not res2.error.is_unknown()):
                merged_err = ParseError.merge(res1.error, res2.error) # res1.error is known
                return ParseResult.error_empty(state, merged_err)
            
            # Otherwise (res2 succeeded, or res2 was a consumed error),
            # the result of res2 takes precedence.
            # If res2 was an empty success, its (likely unknown) error is preserved,
            # and res1.error (which is known) is NOT merged here.
            return res2
        return Parsec(parse)


# --- Applicative Functor style operators ---
    # (&) Sequence, keeping both results
    def __and__(self, other: 'Parsec[U]') -> 'Parsec[Tuple[T, U]]':
        return self.bind(lambda val_t: other.bind(lambda val_u: _pure((val_t, val_u))))

    # (*>) Sequence, keeping right result
    def __gt__(self, other: 'Parsec[U]') -> 'Parsec[U]':
        return self.bind(lambda _: other)

    # (<*) Sequence, keeping left result
    def __lt__(self, other: 'Parsec[U]') -> 'Parsec[T]':
        return self.bind(lambda val_t: other.bind(lambda _: _pure(val_t)))

    # Monadic bind also available as >>
    def __rshift__(self, f: Callable[[T], 'Parsec[U]']) -> 'Parsec[U]':
        return self.bind(f)

    def label(self, msg: str) -> 'Parsec[T]':
        def parse(state: State) -> ParseResult[T]:
            res = self(state) # res is ParseResult[T]

            # Only modify error if self failed *without consuming input* AND the error is *known*.
            if res.error and not res.error.is_unknown() and not res.consumed:
                # Error is at the original state's position, and it's an empty error.
                # Replace existing EXPECT messages or add if none.
                current_messages = res.error.messages
                # Filter out old EXPECT messages, keep others
                non_expect_messages = [m for m in current_messages if m.type != MessageType.EXPECT]
                new_expect_message = Message(MessageType.EXPECT, msg)
                
                # Add the new expect message. Ensure no duplicates if msg was already a non-EXPECT type.
                # A simpler way: just replace all EXPECTs with the new one.
                # Parsec typically clears other expect messages and adds this one.
                final_messages = [m for m in res.error.messages if m.type != MessageType.EXPECT] + [Message(MessageType.EXPECT, msg)]
                
                return ParseResult.error_empty(state, ParseError(state.pos, sorted(list(set(final_messages)))))

            # Otherwise (success, or consumed error, or empty unknown error), return the original result.
            return res
        return Parsec(parse)

    def map(self, f: Callable[[T], U]) -> 'Parsec[U]':
        """
        Maps a function over the result of a successful parser.
        Equivalent to Haskell's fmap or <$>
        p.map(f) is shorthand for p >>= (lambda x: pure(f(x)))
        """
        return self.bind(lambda x: _pure(f(x)))

def _pure(value: T) -> Parsec[T]:
    """Return a parser that succeeds with a value without consuming input."""
    def parse(state: State) -> ParseResult[T]:
        return ParseResult.ok_empty(value, state, ParseError.new_unknown(state.pos)) # Default err is unknown
    return Parsec(parse)
