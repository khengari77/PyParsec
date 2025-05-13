from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple, List, TypeVar, Generic

T = TypeVar('T')  # Generic type for parser results
U = TypeVar('U')

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
    def __init__(self, parse_fn: Callable[[State], Result[T]]): # Input function produces Result[T]
        self.parse_fn = parse_fn

    def __call__(self, state: State) -> Result[T]: # Parsec[T] produces Result[T]
        return self.parse_fn(state)

    # Monadic bind (>>=)
    def bind(self, f: Callable[[T], 'Parsec[U]']) -> 'Parsec[U]':
        # f takes a T (result of self) and returns a new Parsec[U]
        # The whole bind operation then results in a Parsec[U]
        def parse(state: State) -> Result[U]: # The inner parse function will produce Result[U]
            value, new_state, err = self(state) # self(state) produces Result[T]
            if err:
                # If the first parser failed, propagate its state and error.
                # The 'value' part of the tuple should be None, matching Result[U]'s Optional[U].
                return None, new_state, err

            # If the first parser succeeded (err is None), its 'value' (which is of type T)
            # is passed to the function f to get the next parser (which is Parsec[U]).
            next_parser: 'Parsec[U]' = f(value)
            return next_parser(new_state) # Run the next parser, which produces Result[U]
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

    # Sequence (&)
    # self: Parsec[T], other: Parsec[U] -> result: Parsec[Tuple[T, U]]
    def __and__(self, other: 'Parsec[U]') -> 'Parsec[Tuple[T, U]]': # Now returns a Parsec of a Tuple
        def combined(state: State) -> Result[Tuple[T, U]]:
            value1, state1, err1 = self(state) # self is Parsec[T]
            if err1:
                return None, state1, err1

            value2, state2, err2 = other(state1) # other is Parsec[U]
            if err2:
                return None, state2, err2

            return (value1, value2), state2, None # Result is Tuple[T, U]
        return Parsec(combined)

    # Sequence (*>)
    # self: Parsec[T], other: Parsec[U] -> result: Parsec[U]
    def __gt__(self, other: 'Parsec[U]') -> 'Parsec[U]':
        def combined(state: State) -> Result[U]:
            _, state1, err1 = self(state) # self is Parsec[T], its value is discarded
            if err1:
                return None, state1, err1

            value2, state2, err2 = other(state1) # other is Parsec[U]
            if err2:
                return None, state2, err2

            return value2, state2, None
        return Parsec(combined)

    # Sequence (<*)
    # self: Parsec[T], other: Parsec[U] -> result: Parsec[T]
    def __lt__(self, other: 'Parsec[U]') -> 'Parsec[T]':
        def combined(state: State) -> Result[T]:
            value1, state1, err1 = self(state) # self is Parsec[T]
            if err1:
                return None, state1, err1

            _, state2, err2 = other(state1) # other is Parsec[U], its value is discarded
            if err2:
                return None, state2, err2
            
            return value1, state2, None
        return Parsec(combined)


    # Monadic bind also available as >>
    def __rshift__(self, f: Callable[[T], 'Parsec[U]']) -> 'Parsec[U]': # Changed other to f for clarity
        return self.bind(f)
    

    # Label (<?>)
    def label(self, msg: str) -> 'Parsec[T]':
        def parse(state: State) -> Result[T]:
            value, new_state, err = self(state)
            if err and state.input == new_state.input:  # Empty failure
                return None, new_state, ParseError(state.pos, f"expecting {msg}")
            return value, new_state, err
        return Parsec(parse)
