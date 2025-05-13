from .Parsec import Parsec, Result, State, ParseError, SourcePos, T, U
from typing import TypeVar, Callable, Any, Optional, Tuple, List

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


ItemType = TypeVar('ItemType')
AccType = TypeVar('AccType')

def _many_accum(
    # acc_func: (parsed_item, accumulated_value_so_far) -> new_accumulated_value
    acc_func: Callable[[ItemType], Callable[[AccType], AccType]], # Curried form: item -> (acc -> acc)
                                                                  # Or direct: Callable[[ItemType, AccType], AccType]
    # acc_func: Callable[[ItemType, AccType], AccType],
    p: Parsec[ItemType],
    # initial_acc: AccType # We'll try to derive the 'empty' case like Haskell's
    empty_acc_value: AccType # Explicitly provide the value for zero matches
) -> Parsec[AccType]:
    """
    Internal helper to apply parser `p` zero or more times, accumulating results.
    - `acc_func(item, current_acc)` is called for each successfully parsed `item`.
    - `p` must consume input on success to continue the loop, otherwise an error is raised
      to prevent infinite loops.
    - If `p` fails without consuming input, accumulation stops, and `current_acc` is returned.
    - If `p` fails after consuming input, `_many_accum` fails.
    - If `p` never succeeds (even on the first try without consumption), `empty_acc_value` is returned.
    """
    def parse_accum(state_outer: State) -> Result[AccType]:
        
        current_acc: AccType = empty_acc_value
        accum_state: State = state_outer # State from which we attempt the next `p`

        while True:
            state_before_this_p_attempt = accum_state
            
            # Try to parse 'p'
            item, next_state_after_p, err = p(accum_state)

            if err:
                # 'p' failed
                if accum_state.pos == next_state_after_p.pos: # Failed without consuming input
                    # Stop accumulation, succeed with current_acc and the state *before* this failed 'p'
                    return current_acc, accum_state, None
                else: # Failed *after* consuming input
                    # _many_accum fails, propagate error and state from 'p'
                    return None, next_state_after_p, err
            
            # 'p' succeeded, 'item' is the parsed value
            # Check if 'p' consumed input
            if accum_state.pos == next_state_after_p.pos:
                # 'p' succeeded but consumed no input. This causes an infinite loop.
                return None, accum_state, ParseError(
                    accum_state.pos,
                    "_many_accum: Applied parser succeeded without consuming input, " +
                    "which would lead to an infinite loop."
                )

            # 'p' succeeded and consumed input. Apply accumulator.
            current_acc = acc_func(item, current_acc)
            accum_state = next_state_after_p
            # Loop again from the new state

    return Parsec(parse_accum)


def many(p: Parsec[T]) -> Parsec[List[T]]:
    """Parse zero or more occurrences of `p`."""
    # Accumulator function: appends item to list (builds in forward order)
    # (item_parsed, list_built_so_far) -> new_list_built_so_far
    acc_list_append = lambda item, lst: lst + [item] 
    
    # _many_accum will give a Parsec[List[T]] where the list is already in the correct order.
    # The initial value for the accumulator is an empty list.
    return _many_accum(acc_list_append, p, [])


def skip_many(parser: Parsec[Any]) -> Parsec[None]:
    """Skips zero or more occurrences of `parser`."""
    # Accumulator function: does nothing, result type is arbitrary (e.g., None)
    # (parsed_item, current_accumulator_is_None) -> new_accumulator_is_None
    do_nothing_acc = lambda item, acc_val: None
    
    # _many_accum will produce Parsec[None]
    # Initial/empty value for accumulator is None
    return _many_accum(do_nothing_acc, parser, None)
    # The result of _many_accum here is already Parsec[None], so no further bind needed
    # unlike the Haskell version that might use `[]` as a dummy accumulator value type.


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

