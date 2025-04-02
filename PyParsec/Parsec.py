from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple, List, TypeVar, Generic

T = TypeVar('T')  # Generic type for parser results

@dataclass
class SourcePos:
    """Represents the current position in the input stream."""
    line: int = 1
    column: int = 1
    name: str = ""

    def update(self, token: str) -> 'SourcePos':
        """Update position based on a token (e.g., character)."""
        if token == '\n':
            return SourcePos(self.line + 1, 1, self.name)
        return SourcePos(self.line, self.column + 1, self.name)

    def __str__(self) -> str:
        return f"{self.name} line {self.line}, column {self.column}"

@dataclass
class State(Generic[T]):
    """Parser state: input stream, position, and user state."""
    input: str  # Simplified to string input; could be generalized
    pos: SourcePos
    user: Any

@dataclass
class ParseError:
    """Represents a parsing error with a message and position."""
    pos: SourcePos
    message: str

    def __str__(self) -> str:
        return f"Parse error at {self.pos}: {self.message}"

Result = Tuple[Optional[T], State, Optional[ParseError]]
# (value, new_state, error): None for value or error indicates failure or no error

class Parsec(Generic[T]):
    """A parser combinator that processes input and returns a result."""
    def __init__(self, parse_fn: Callable[[State], Result[T]]):
        self.parse_fn = parse_fn

    def __call__(self, state: State) -> Result[T]:
        return self.parse_fn(state)

    # Monadic bind (>>=)
    def bind(self, f: Callable[[T], 'Parsec[T]']) -> 'Parsec[T]':
        def parse(state: State) -> Result[Any]:
            value, new_state, err = self(state)
            if err:
                return None, new_state, err
            if value is None:
                return None, new_state, ParseError(new_state.pos, "No value")
            next_parser = f(value)
            return next_parser(new_state)
        return Parsec(parse)

    # Alternative (<|>)
    def __or__(self, other: 'Parsec[T]') -> 'Parsec[T]':
        def parse(state: State) -> Result[T]:
            value, new_state, err = self(state)
            if value is not None and not err:
                return value, new_state, None
            # Only try other if no input was consumed
            if state.input == new_state.input:
                return other(state)
            return None, new_state, err
        return Parsec(parse)

    # Sequence (<*>)
    def __and__(self, other: 'Parsec[T]') -> 'Parsec[T]':
        def combined(state: State) -> Result[T]:
            value1, state1, err1 = self(state)
            if err1:
                return None, state1, err1

            value2, state2, err2 = other(state1)
            if err2:
                return None, state2, err2

            return (value1, value2), state2, None
        return Parsec(combined)

    # Sequence (*>)
    def __gt__(self, other: 'Parsec[T]') -> 'Parsec[T]':
        def combined(state: State) -> Result[T]:
            value1, state1, err1 = self(state)
            if err1:
                return None, state1, err1

            _, state2, err2 = other(state1)
            if err2:
                return None, state2, err2
            
            return value1, state2, None
        return Parsec(combined)

    def __lt__(self, other: 'Parsec[T]') -> 'Parsec[T]':
        def combined(state: State) -> Result[T]:
            _, state1, err1 = self(state)
            if err1:
                return None, state1, err1

            value2, state2, err2 = other(state1)
            if err2:
                return None, state2, err2

            return value2, state2, None
        return Parsec(combined)

    def __invert__(self) -> 'Parsec[T]':
        def inverted(state: State) -> Result[T]:
            value, new_state, err = self(state)
            if err:
                return None, new_state, err
            if value is None:
                return None, new_state, ParseError(new_state.pos, "No value")
            
        return Parsec(inverted)


    def __rshift__(self, other: 'Parsec[T]') -> 'Parsec[T]':
        return self.bind(other)

    # Label (<?>)
    def label(self, msg: str) -> 'Parsec[T]':
        def parse(state: State) -> Result[T]:
            value, new_state, err = self(state)
            if err and state.input == new_state.input:  # Empty failure
                return None, new_state, ParseError(state.pos, f"expecting {msg}")
            return value, new_state, err
        return Parsec(parse)
