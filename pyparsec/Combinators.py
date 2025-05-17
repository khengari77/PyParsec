from typing import List, Optional, Callable, Any, TypeVar, Union
from .Parsec import Parsec, State, ParseError, SourcePos, ParseResult, T, U, MessageType, Reply
from .Prim import pure, fail, try_parse, token, many, look_ahead


# 1. choice: Tries parsers in order until one succeeds
def choice(parsers: List[Parsec[T]]) -> Parsec[T]:
    """
    Applies a list of parsers in order until one succeeds.
    Returns the value of the succeeding parser, or fails if none succeed.
    """
    if not parsers:
        return fail("no alternatives")
    result = parsers[0]
    for p in parsers[1:]:
        result = result | p
    return result

# 2. count: Parses n occurrences of a parser
def count(n: int, p: Parsec[T]) -> Parsec[List[T]]:
    if n <= 0:
        return pure([])
    def parse(state_initial: State) -> ParseResult[List[T]]: # Changed
        results = []
        current_state = state_initial
        consumed_overall = False
        last_error: Optional[ParseError] = ParseError.new_unknown(state_initial.pos)

        for i in range(n):
            res_p = p(current_state) # res_p is ParseResult[T]
            consumed_overall = consumed_overall or res_p.consumed

            if res_p.error and not res_p.error.is_unknown():
                # p failed with a known error
                # Propagate error with its consumption status, or overall if p was empty error
                if res_p.consumed:
                    return ParseResult.error_consumed(res_p.state, res_p.error)
                else: # p's error was empty, but count might have consumed overall
                    if consumed_overall:
                         return ParseResult.error_consumed(current_state, res_p.error) # Error at current_state before this failing p
                    else:
                         return ParseResult.error_empty(state_initial, res_p.error)


            if res_p.value is None: # Should be caught by above if error is significant
                 # Failsafe: if no value and error is unknown, create a generic failure message
                err_msg = ParseError.new_message(current_state.pos, MessageType.MESSAGE, f"count: parser failed at iteration {i+1}")
                if consumed_overall:
                    return ParseResult.error_consumed(current_state, err_msg)
                else:
                    return ParseResult.error_empty(state_initial, err_msg)


            results.append(res_p.value)
            current_state = res_p.state
            last_error = ParseError.merge(last_error, res_p.error or ParseError.new_unknown(current_state.pos))


        # All n iterations succeeded
        if consumed_overall:
            return ParseResult.ok_consumed(results, current_state, last_error)
        else:
            return ParseResult.ok_empty(results, current_state, last_error) # current_state would be state_initial
    return Parsec(parse)
# 3. between: Parses an opening parser, a main parser, and a closing parser
def between(open: Parsec[Any], close: Parsec[Any], p: Parsec[T]) -> Parsec[T]:
    """
    Parses 'open', then 'p', then 'close', returning the result of 'p'.
    """
    return open.bind(lambda _: p.bind(lambda x: close.bind(lambda _: pure(x))))

# 4. option: Tries a parser, returning a default value on failure
def option(x: T, p: Parsec[T]) -> Parsec[T]:
    """
    Tries parser p; returns its result if successful, else x if it fails without consuming input.
    """
    return p | pure(x)

# 5. optionMaybe: Tries a parser, returning Optional[T]
def option_maybe(p: Parsec[T]) -> Parsec[Optional[T]]:
    """
    Tries parser p; returns the value if successful, else None if it fails without consuming input.
    Uses Optional[T] to represent Haskell's Maybe.
    """
    return p | pure(None)

# 6. optional: Tries a parser, discarding the result
def optional(p: Parsec[T]) -> Parsec[None]:
    """
    Tries parser p; returns None whether it succeeds or fails (if no input consumed).
    """
    return p.bind(lambda _: pure(None)) | pure(None)

# 7. skipMany1: Skips one or more occurrences of a parser
def skip_many1(p: Parsec[Any]) -> Parsec[None]:
    """
    Applies parser p one or more times, discarding results.
    """
    return p.bind(lambda _: many(p).bind(lambda _: pure(None)))

# 8. many1: Applies a parser one or more times
def many1(p: Parsec[T]) -> Parsec[List[T]]:
    """
    Applies parser p one or more times, returning a list of results.
    """
    return p.bind(lambda x: many(p).bind(lambda xs: pure([x] + xs)))

# 9. sepBy: Parses zero or more occurrences separated by a separator
def sep_by(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """
    Parses zero or more occurrences of p separated by sep, returning a list of p's results.
    """
    return sep_by1(p, sep) | pure([])

# 10. sepBy1: Parses one or more occurrences separated by a separator
def sep_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """
    Parses one or more occurrences of p separated by sep, returning a list of p's results.
    """
    return p.bind(lambda x: many(sep.bind(lambda _: p)).bind(lambda xs: pure([x] + xs)))

# 11. endBy: Parses zero or more occurrences separated and ended by a separator
def end_by(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """
    Parses zero or more occurrences of p, each followed by sep, returning a list of p's results.
    """
    return many(p.bind(lambda x: sep.bind(lambda _: pure(x))))

# 12. endBy1: Parses one or more occurrences separated and ended by a separator
def end_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """
    Parses one or more occurrences of p, each followed by sep, returning a list of p's results.
    """
    return many1(p.bind(lambda x: sep.bind(lambda _: pure(x))))

# 13. sepEndBy: Parses zero or more occurrences separated and optionally ended by a separator
def sep_end_by(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """
    Parses zero or more occurrences of p separated and optionally ended by sep.
    """
    # sep_end_by1 will be defined below. This creates a mutual recursion.
    return sep_end_by1(p, sep) | pure([])


# 14. sepEndBy1: Parses one or more occurrences separated and optionally ended by a separator
def sep_end_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """
    Parses one or more occurrences of p separated and optionally ended by sep.
    """
    def parse_re_parser(first_val: T) -> Parsec[List[T]]:
        rest_parser = option([], sep >> sep_end_by(p, sep))
        return rest_parser.bind(lambda rest_list: pure([first_val] + rest_list))

    return p.bind(parse_re_parser)

# 15. chainl: Left-associative operator chain with a default value
def chainl(p: Parsec[T], op: Parsec[Callable[[T, T], T]], x: T) -> Parsec[T]:
    """
    Parses zero or more p separated by op, applying op left-associatively; returns x if none parsed.
    """
    return chainl1(p, op) | pure(x)

# 16. chainl1: Left-associative operator chain
def chainl1(p: Parsec[T], op: Parsec[Callable[[T, T], T]]) -> Parsec[T]:
    """
    Iterative version of chainl1.
    Parses one or more p separated by op, applying op left-associatively.
    """
    def parse(initial_state: State) -> ParseResult[T]:
        # 1. Parse the first 'p'
        res_first_p = p(initial_state)

        if res_first_p.value is None:
            # Failed to parse even the first 'p', so chainl1 fails
            return res_first_p

        # Successfully parsed the first 'p'
        current_value = res_first_p.value
        current_state = res_first_p.state
        consumed_overall = res_first_p.consumed
        # Accumulate errors from successful optional parts (op and p)
        # Start with the error from the first p (likely unknown if p succeeded)
        accumulated_error = res_first_p.error or ParseError.new_unknown(res_first_p.state.pos)


        # 2. Loop to parse 'op' and 'p' repeatedly
        while True:
            # Save state before trying 'op' and 'p' in this iteration
            state_before_op = current_state

            # Try to parse 'op'
            res_op = op(state_before_op)

            if res_op.value is None:
                # 'op' failed. This means the chain ends.
                # The current_value is the final result.
                # Merge the error from the failed 'op' attempt if it's an "empty" error.
                # If 'op' failed "consumed", that error should not be part of a successful chainl1.
                # However, 'op' failing empty is common (e.g. no more operators).
                final_error = ParseError.merge(accumulated_error, res_op.error) if not res_op.consumed else accumulated_error
                return ParseResult(
                    Reply(current_value, current_state, final_error), # State is where op failed or last p succeeded
                    consumed_overall # Overall consumption up to the last successful p
                )

            # 'op' succeeded
            func_op = res_op.value
            state_after_op = res_op.state
            consumed_in_op = res_op.consumed
            accumulated_error = ParseError.merge(accumulated_error, res_op.error or ParseError.new_unknown(res_op.state.pos))


            # Try to parse 'p'
            res_next_p = p(state_after_op)

            if res_next_p.value is None:
                # 'p' (after a successful 'op') failed. This is an error for chainl1.
                # The whole chainl1 should fail here because 'op' was expecting a 'p'.
                # The error should be from res_next_p, merged with previous significant errors.
                # Consumption by op matters.
                final_error = ParseError.merge(accumulated_error, res_next_p.error)
                return ParseResult(
                    Reply(None, res_next_p.state, final_error), # Error occurred at res_next_p.state
                    consumed_overall or consumed_in_op or res_next_p.consumed
                )

            # 'op' and 'p' both succeeded in this iteration
            next_operand = res_next_p.value
            current_state = res_next_p.state # Update state for the next iteration
            
            # Update overall consumption
            consumed_overall = consumed_overall or consumed_in_op or res_next_p.consumed
            accumulated_error = ParseError.merge(accumulated_error, res_next_p.error or ParseError.new_unknown(res_next_p.state.pos))

            # Apply the operator
            try:
                current_value = func_op(current_value, next_operand)
            except Exception as e: # Catch runtime errors from the operator function itself
                # This is a runtime failure, not a parse failure in the traditional sense,
                # but we can represent it as a consumed parse error.
                err_msg = f"Runtime error in operator: {e}"
                op_runtime_error = ParseError.new_message(state_after_op.pos, MessageType.MESSAGE, err_msg) # Error at op's position
                return ParseResult.error_consumed(state_after_op, op_runtime_error)

            # Loop back to try another 'op' and 'p'

    return Parsec(parse)



# 17. chainr: Right-associative operator chain with a default value
def chainr(p: Parsec[T], op: Parsec[Callable[[T, T], T]], x: T) -> Parsec[T]:
    """
    Parses zero or more p separated by op, applying op right-associatively; returns x if none parsed.
    """
    return chainr1(p, op) | pure(x)

# 18. chainr1: Right-associative operator chain
def chainr1(p: Parsec[T], op: Parsec[Callable[[T, T], T]]) -> Parsec[T]:
    """
    Parses one or more p separated by op, applying op right-associatively. (Iterative)
    """
    def apply_right_associative(scan_results_val: List[Union[T, Callable[[T, T], T]]]) -> T:
        # scan_results_val = [term1, op1, term2, op2, ..., termN]
        if not scan_results_val:
            raise ValueError("chainr1: _scan_op_chain returned empty list")

        # If only one term, no operators
        if len(scan_results_val) == 1:
            return scan_results_val[0] # type: ignore

        # Work from the right: last_term = termN, prev_op = op(N-1), prev_term = term(N-1)
        # acc = op(N-1)(term(N-1), termN)
        # acc = op(N-2)(term(N-2), acc)
        
        # Last element is always a term
        acc_val = scan_results_val[-1]
        # if not isinstance(acc_val, (int, float, str)) and not callable(acc_val): # Basic check
        #      pass

        idx = len(scan_results_val) - 2 # Index of the last operator
        while idx > 0: # op_func is at idx, term is at idx-1
            op_func = scan_results_val[idx]
            if not callable(op_func):
                 raise ValueError(f"chainr1: Expected operator function, got {op_func}")

            term_val = scan_results_val[idx-1]
            # if not isinstance(term_val, (int, float, str)) and not callable(term_val): # Basic check
            #      pass
            
            acc_val = op_func(term_val, acc_val) # type: ignore
            idx -= 2
        return acc_val # type: ignore

    return _scan_op_chain(p, op) >> (lambda scanned_list: pure(apply_right_associative(scanned_list)))

# 19. eof: Succeeds only at the end of input
def eof() -> Parsec[None]:
    """
    Succeeds only if no input remains, labeled as 'end of input'.
    """
    return not_followed_by(any_token()).label("end of input")

# 20. anyToken: Accepts any single token
def any_token() -> Parsec[str]:
    """
    Accepts any single character from the input, returning it.
    """
    return token(lambda t: str(t), lambda t: t if t else None)  # Assumes token is from previous implementation

# 21. notFollowedBy: Succeeds if a parser fails without consuming input
def not_followed_by(p: Parsec[Any]) -> Parsec[None]:
    def parse(state: State) -> ParseResult[None]:
        # Attempt p without consuming input from not_followed_by's perspective.
        # look_ahead(p) attempts p. If p succeeds, look_ahead makes it an empty success.
        # If p fails (consumed or empty), look_ahead propagates that failure.
        # try_parse then ensures that any failure from look_ahead(p) becomes an empty failure.
        res_attempt_p = try_parse(look_ahead(p))(state)

        if res_attempt_p.error and not res_attempt_p.error.is_unknown():
            # p effectively failed (its failure was made empty by try_parse(look_ahead(...))).
            # So, not_followed_by SUCCEEDS.
            return ParseResult.ok_empty(None, state, ParseError.new_unknown(state.pos))
        else:
            # p effectively succeeded (res_attempt_p.value is its result).
            # So, not_followed_by FAILS.
            # Create a generic "unexpected" message.
            # Parsec uses `show` of p's result. A generic message is often sufficient.
            err_text = f"unexpected {str(res_attempt_p.value)}" if res_attempt_p.value is not None else "unexpected successful parse"
            return ParseResult.error_empty(state, ParseError.new_message(state.pos, MessageType.UNEXPECT, err_text))
    return Parsec(parse).label(f"not followed by {p!r}") # Optional: add a label

# 22. manyTill: Parses p zero or more times until end succeeds
def many_till(p: Parsec[T], end: Parsec[Any]) -> Parsec[List[T]]:
    """
    Applies p zero or more times until end succeeds, returning a list of p's results.
    """
    def scan() -> Parsec[List[T]]:
        return end.bind(lambda _: pure([])) | p.bind(lambda x: scan().bind(lambda xs: pure([x] + xs)))
    return scan()

# 23. lookAhead: Already implemented as look_ahead in the previous code
# Assuming look_ahead: Parsec[T] -> Parsec[T] is available

# 24. parserTrace: Debugging parser that prints the remaining input
def parser_trace(label_str: str) -> Parsec[None]: # Renamed label to label_str
    def parse(state: State) -> ParseResult[None]:
        print(f"{label_str}: \"{state.input[:30]}{'...' if len(state.input)>30 else ''}\" at {state.pos}")
        # parser_trace does not consume and always "succeeds" with None (empty ok)
        return ParseResult.ok_empty(None, state, ParseError.new_unknown(state.pos))
    return Parsec(parse)

# 25. parserTraced: Debugging parser that traces execution and backtracking
def parser_traced(label_str: str, p: Parsec[T]) -> Parsec[T]:
    # parser_trace >> (try_parse(p) | (parser_trace(f"{label_str} backtracked") >> fail(f"{label_str} failed")))
    # This composition should work fine as underlying ops are updated.
    trace_enter = parser_trace(label_str)
    
    def on_backtrack(_): # Value from parser_trace is None
        # This fail will produce an empty error because it's on the RHS of an OR
        # and parser_trace(backtracked) is empty.
        return fail(f"{label_str} backtracked and parser failed")

    # if p fails after consuming, try_parse turns it into an empty error.
    # The choice operator `|` will then try the backtrack path.
    # If p succeeds, its result is passed through.
    return trace_enter >> (try_parse(p) | (parser_trace(f"{label_str} backtracked") >> Parsec(lambda s: on_backtrack(s))))


# Helper to define the type of operator function more clearly
OpFuncType = Callable[[T, T], T] # Example for binary ops like in chainl/r

def _scan_op_chain(
    term_parser: Parsec[T],
    op_parser: Parsec[OpFuncType]  # Operator parser returns the function itself
) -> Parsec[List[Union[T, OpFuncType]]]:
    """
    Parses `term_parser (op_parser term_parser)*` and returns a flat list
    of alternating term results and operator functions: 
    [term1_val, op1_func, term2_val, op2_func, ..., termN_val].
    Handles consumption and error merging during the scan.
    Fails if the first term_parser fails.
    """
    def parse(initial_state: State) -> ParseResult[List[Union[T, OpFuncType]]]:
        # 1. Parse the first term_parser
        res_first_term = term_parser(initial_state)
        if res_first_term.value is None: # First term failed
            return res_first_term # Propagate its error and consumption

        # Successfully parsed the first term
        scan_results: List[Union[T, OpFuncType]] = [res_first_term.value]
        current_state = res_first_term.state
        overall_consumed = res_first_term.consumed
        # Error from the first term (likely unknown if it succeeded)
        accumulated_error = res_first_term.error or ParseError.new_unknown(current_state.pos)

        while True:
            # 2. Try to parse op_parser
            # We are at current_state, which is after the last successful term/op
            op_attempt_state = current_state 
            res_op = op_parser(op_attempt_state)
            
            # Merge op's error (even if it's an unknown error from a successful empty op parse)
            accumulated_error = ParseError.merge(accumulated_error, res_op.error)

            # If op_parser failed EMPTY, the chain is complete.
            if res_op.value is None and not res_op.consumed:
                if overall_consumed:
                    return ParseResult.ok_consumed(scan_results, op_attempt_state, accumulated_error)
                else: # Nothing consumed overall, should be initial_state
                    return ParseResult.ok_empty(scan_results, initial_state, accumulated_error)

            # If op_parser failed CONSUMED, the whole _scan_op_chain fails.
            if res_op.value is None and res_op.consumed:
                overall_consumed = True # op_parser itself consumed
                return ParseResult.error_consumed(res_op.state, accumulated_error)

            # op_parser succeeded. It might have consumed or not.
            op_func = res_op.value
            overall_consumed = overall_consumed or res_op.consumed
            current_state = res_op.state # State after successful op_parser

            # 3. Try to parse the next term_parser (must follow an op)
            term_after_op_attempt_state = current_state
            res_next_term = term_parser(term_after_op_attempt_state)
            
            # Merge next term's error
            accumulated_error = ParseError.merge(accumulated_error, res_next_term.error)

            # If the next term_parser fails, the chain is malformed (op without RHS).
            if res_next_term.value is None:
                overall_consumed = overall_consumed or res_next_term.consumed # next_term might have consumed
                if overall_consumed:
                    return ParseResult.error_consumed(res_next_term.state, accumulated_error)
                else:
                    # This means: first_term (ok, empty), op (ok, empty), next_term (fail, empty)
                    return ParseResult.error_empty(initial_state, accumulated_error)
            
            # Both op_parser and subsequent term_parser succeeded.
            scan_results.append(op_func)
            scan_results.append(res_next_term.value)
            
            overall_consumed = overall_consumed or res_next_term.consumed
            current_state = res_next_term.state
            # Loop again to find another op

    return Parsec(parse)
