from .Parsec import Parsec, State, ParseError, SourcePos, MessageType, Message, Reply, ParseResult, T, U
from typing import TypeVar, Callable, Any, Optional, Tuple, List

ItemType = TypeVar('ItemType')
AccType = TypeVar('AccType')

def pure(value: T) -> Parsec[T]: # Moved from Parsec.py or ensure it's defined first
    """Return a parser that succeeds with a value without consuming input."""
    def parse(state: State) -> ParseResult[T]:
        return ParseResult.ok_empty(value, state, ParseError.new_unknown(state.pos))
    return Parsec(parse)

def fail(msg: str) -> Parsec[Any]:
    """A parser that always fails with a message."""
    def parse(state: State) -> ParseResult[Any]:
        return ParseResult.error_empty(state, ParseError.new_message(state.pos, MessageType.MESSAGE, msg))
    return Parsec(parse)

def token(show_tok: Callable[[str], str], test_tok: Callable[[str], Optional[T]]) -> Parsec[T]:
    """Parse a single token matching a condition."""
    def parse(state: State) -> ParseResult[T]:
        if not state.input:
            # Failed to get a token (EOF), empty error
            return ParseResult.error_empty(state, ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, ""))

        tok_val = state.input[0]
        result_val = test_tok(tok_val)

        if result_val is None:
            # Token didn't match, empty error
            return ParseResult.error_empty(state, ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, show_tok(tok_val)))

        # Token matched and consumed
        new_pos = state.pos.update(tok_val) # Assuming SourcePos.update handles single char
        new_state = State(state.input[1:], new_pos, state.user)
        return ParseResult.ok_consumed(result_val, new_state, ParseError.new_unknown(new_pos))
    return Parsec(parse)

def try_parse(parser: Parsec[T]) -> Parsec[T]:
    """Try a parser, converting a consumed error into an empty error."""
    def parse(state: State) -> ParseResult[T]:
        res = parser(state) # res is ParseResult[T]
        if res.error and res.consumed:
            # If parser failed AND consumed input, create an empty error using original state
            return ParseResult.error_empty(state, res.error)
        
        # Otherwise (success OR empty error), return the result as is.
        # If it was success (consumed or empty), consumption status is preserved.
        # If it was an empty error, it's already an empty error.
        return res
    return Parsec(parse)


def look_ahead(parser: Parsec[T]) -> Parsec[T]:
    """Parse without consuming input."""
    def parse(state: State) -> ParseResult[T]:
        res = parser(state) # res is ParseResult[T]

        # If parser errored, it's an empty error from the original state
        if res.value is None:
            return ParseResult.error_empty(state, res.error)
        
        # If parser succeeded, return its value but with the original state (empty success)
        # The error in the reply should be unknown at the original position.
        return ParseResult.ok_empty(res.value, state, ParseError.new_unknown(state.pos))
    return Parsec(parse)

ItemType = TypeVar('ItemType')
AccType = TypeVar('AccType')

def _many_accum(
    acc_func: Callable[[ItemType, AccType], AccType],
    p: Parsec[ItemType],
    empty_acc_value: AccType
) -> Parsec[AccType]:
    def parse_accum(state_outer: State) -> ParseResult[AccType]:
        current_acc: AccType = empty_acc_value
        accum_state: State = state_outer # Current state for the next attempt of p
        consumed_overall: bool = False # Track if any p has consumed input

        while True:
            # Try to parse 'p'
            res_p = p(accum_state) # res_p is ParseResult[ItemType]

            consumed_overall = consumed_overall or res_p.consumed

            if res_p.value is None:
                # 'p' failed
                if not res_p.consumed: # Failed without consuming input (empty error from p)
                    # Stop accumulation, succeed with current_acc.
                    # The state is accum_state (before this failed 'p').
                    # Report as empty success if nothing was ever consumed.
                    # Report as consumed success if *any* previous iteration of p consumed.
                    if consumed_overall:
                        return ParseResult.ok_consumed(current_acc, accum_state, ParseError.new_unknown(accum_state.pos))
                    else:
                        return ParseResult.ok_empty(current_acc, accum_state, ParseError.new_unknown(accum_state.pos))
                else: # Failed *after* consuming input (consumed error from p)
                    # _many_accum fails, propagate error and state from 'p'. It's a consumed error.
                    return res_p

            # 'p' succeeded, res_p.value is the parsed item
            # Check if 'p' (this specific iteration) consumed input
            if not res_p.consumed:
                # 'p' succeeded but consumed no input in this iteration. This causes an infinite loop.
                # Report as a consumed error because _many_accum itself is trying to make progress.
                return ParseResult.error_consumed(
                    accum_state, # Error at the point of non-consumption
                    ParseError.new_message(
                        accum_state.pos,
                        MessageType.MESSAGE,
                        "_many_accum: Applied parser succeeded without consuming input."
                    )
                )

            # 'p' succeeded and consumed input for this iteration. Apply accumulator.
            current_acc = acc_func(res_p.value, current_acc) # type: ignore
            accum_state = res_p.state # Update state for the next loop
            # Loop again
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


def run_parser(parser: Parsec[T], 
               input_str: str, 
               user_state: Any = None, 
               source_name: str = "") -> Tuple[Optional[T], Optional[ParseError]]:
    initial_state = State(input_str, SourcePos(name=source_name), user_state)
    parse_result = parser(initial_state)
    return parse_result.value, parse_result.error

def parse_test(parser: Parsec[T], input: str) -> None:
    """Test a parser and print the result."""
    value, err = run_parser(parser, input)
    if err:
        print(err)
    else:
        print(value)

# tokens and tokens_prime need to correctly determine consumption
def tokens(show_tokens_fn: Callable[[str], str], # Renamed for clarity
           next_pos_fn: Callable[[SourcePos, str], SourcePos], # Renamed
           s_list: List[str] # Renamed
           ) -> Parsec[str]:
    def parse(state: State) -> ParseResult[str]:
        input_str = state.input
        to_match_str = ''.join(s_list)

        if not to_match_str: # Parsing an empty string always succeeds, consumes nothing
            return ParseResult.ok_empty("", state, ParseError.new_unknown(state.pos))

        if input_str.startswith(to_match_str):
            matched_str = to_match_str
            
            # Calculate new position by iterating through matched_str
            current_pos = state.pos
            for char_in_matched in matched_str:
                current_pos = current_pos.update(char_in_matched)
            new_pos_val = current_pos # Use the iterated position

            new_state_val = State(input_str[len(matched_str):], new_pos_val, state.user)
            # tokens always consumes if it matches a non-empty string
            return ParseResult.ok_consumed(matched_str, new_state_val, ParseError.new_unknown(new_pos_val))
        else:
            # Failed to match, this is an empty error
            expected_msg = show_tokens_fn(to_match_str)
            # Determine what was actually found for the SysUnexpect message
            len_to_match = len(to_match_str)
            actual_found = input_str[:len_to_match] if len(input_str) >= len_to_match else input_str
            if not actual_found and not input_str : # EOF
                actual_msg_text = ""
            else:
                actual_msg_text = show_tokens_fn(actual_found) if actual_found else ""


            err = ParseError(state.pos, [
                Message(MessageType.EXPECT, expected_msg),
                Message(MessageType.SYS_UNEXPECT, actual_msg_text)
            ])
            return ParseResult.error_empty(state, err)
    return Parsec(parse)

def tokens_prime(show_tokens_fn: Callable[[str], str],
                 _next_pos_fn: Callable[[SourcePos, str], SourcePos], # next_pos not strictly needed
                 s_list: List[str]
                 ) -> Parsec[str]:
    def parse(state: State) -> ParseResult[str]:
        input_str = state.input
        to_match_str = ''.join(s_list)

        if not to_match_str: # Matching empty string, empty success
            return ParseResult.ok_empty("", state, ParseError.new_unknown(state.pos))

        if input_str.startswith(to_match_str):
            # Matched, but tokens_prime is non-consuming success
            return ParseResult.ok_empty(to_match_str, state, ParseError.new_unknown(state.pos))
        else:
            # Failed to match, empty error
            expected_msg = show_tokens_fn(to_match_str)
            len_to_match = len(to_match_str)
            actual_found = input_str[:len_to_match] if len(input_str) >= len_to_match else input_str
            if not actual_found and not input_str : # EOF
                actual_msg_text = ""
            else:
                actual_msg_text = show_tokens_fn(actual_found) if actual_found else ""


            err = ParseError(state.pos, [
                Message(MessageType.EXPECT, expected_msg),
                Message(MessageType.SYS_UNEXPECT, actual_msg_text)
            ])
            return ParseResult.error_empty(state, err)
    return Parsec(parse)
