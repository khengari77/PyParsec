from .Parsec import Parsec, Result, State, ParseError, SourcePos
from typing import TypeVar, Callable, Any, Optional, Tuple, List

T = TypeVar('T')

def pure(value: T) -> Parsec[T]:
    """Return a parser that succeeds with a value without consuming input."""
    def parse(state: State) -> Result[T]:
        return value, state, None
    return Parsec(parse)

def fail(msg: str) -> Parsec[Any]:
    """A parser that always fails with a message."""
    def parse(state: State) -> Result[Any]:
        return None, state, ParseError(state.pos, msg)
    return Parsec(parse)

def try_parse(parser: Parsec[T]) -> Parsec[T]:
    """Try a parser, resetting input consumption on failure."""
    def parse(state: State) -> Result[T]:
        value, new_state, err = parser(state)
        if err:
            return None, state, err  # Reset state on error
        return value, new_state, err
    return Parsec(parse)

def look_ahead(parser: Parsec[T]) -> Parsec[T]:
    """Parse without consuming input."""
    def parse(state: State) -> Result[T]:
        value, new_state, err = parser(state)
        if err:
            return None, state, err
        return value, state, None
    return Parsec(parse)

def token(show_tok: Callable[[str], str], test_tok: Callable[[str], Optional[T]]) -> Parsec[T]:
    """Parse a single token matching a condition."""
    def parse(state: State) -> Result[T]:
        if not state.input:
            return None, state, ParseError(state.pos, "unexpected EOF")
        token = state.input[0]
        result = test_tok(token)
        if result is None:
            return None, state, ParseError(state.pos, f"unexpected {show_tok(token)}")
        new_pos = state.pos.update(token)
        new_state = State(state.input[1:], new_pos, state.user)
        return result, new_state, None
    return Parsec(parse)

def many(parser: Parsec[T]) -> Parsec[List[T]]:
    """Parse zero or more occurrences."""
    def parse(state: State) -> Result[List[T]]:
        results = []
        current_state = state
        while True:
            value, new_state, err = parser(current_state)
            if err or value is None:
                return results, current_state, None
            results.append(value)
            current_state = new_state
    return Parsec(parse)


def run_parser(parser: Parsec[T], input: str, user_state: Any = None, source_name: str = "") -> Tuple[Optional[T], Optional[ParseError]]:
    """Run a parser on an input string."""
    initial_state = State(input, SourcePos(name=source_name), user_state)
    value, final_state, err = parser(initial_state)
    return value, err


def parse_test(parser: Parsec[T], input: str) -> None:
    """Test a parser and print the result."""
    value, err = run_parser(parser, input)
    if err:
        print(err)
    else:
        print(value)



# Implementation of tokens
def tokens(show_tokens: Callable[[str], str], next_pos: Callable[[SourcePos, str], SourcePos], s: List[str]) -> Parsec[str]:
    """
    Parses a sequence of characters matching the list s, consuming the input if successful.
    
    Args:
        show_tokens: Function to format tokens for error messages.
        next_pos: Function to compute the new position after consuming tokens.
        s: List of characters to match.
    
    Returns:
        Parsec parser that returns the matched string.
    """
    def parse(state: State) -> Result[str]:
        input_str = state.input
        to_match = ''.join(s)  # Convert list of characters to string
        if input_str.startswith(to_match):
            matched = to_match
            new_pos = next_pos(state.pos, matched)
            new_state = State(input_str[len(matched):], new_pos, state.user)
            return matched, new_state, None
        else:
            expected = show_tokens(to_match)
            actual = input_str[:len(to_match)] if len(input_str) >= len(to_match) else "EOF"
            error_msg = f"expected {expected}, got '{actual}'"
            return None, state, ParseError(state.pos, error_msg)
    return Parsec(parse)

# Implementation of tokens'
def tokens_prime(show_tokens: Callable[[str], str], next_pos: Callable[[SourcePos, str], SourcePos], s: List[str]) -> Parsec[str]:
    """
    Parses a sequence of characters matching the list s without consuming input on success.
    
    Args:
        show_tokens: Function to format tokens for error messages.
        next_pos: Function to compute the new position (not used here since input isn't consumed).
        s: List of characters to match.
    
    Returns:
        Parsec parser that returns the matched string without advancing the state.
    """
    def parse(state: State) -> Result[str]:
        input_str = state.input
        to_match = ''.join(s)
        if input_str.startswith(to_match):
            matched = to_match
            # Do not consume input, return original state
            return matched, state, None
        else:
            expected = show_tokens(to_match)
            actual = input_str[:len(to_match)] if len(input_str) >= len(to_match) else "EOF"
            error_msg = f"expected {expected}, got '{actual}'"
            return None, state, ParseError(state.pos, error_msg)
    return Parsec(parse)

