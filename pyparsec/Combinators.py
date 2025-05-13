from typing import List, Optional, Callable, Any, TypeVar
from .Parsec import Parsec, State, ParseError, SourcePos, ParseResult, T, U, MessageType
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


def many1(p: Parsec[T]) -> Parsec[List[T]]:
    """
    Applies parser p one or more times, returning a list of results.
    """
    # p must succeed once
    # then, many(p) parses zero or more additional items
    def combine(first_item):
        def combine_with_rest(rest_items):
            return pure([first_item] + rest_items)
        return many(p).bind(combine_with_rest)

    return p.bind(combine)

    # Or more compactly:
    # return p.bind(lambda x: many(p).bind(lambda xs: pure([x] + xs)))
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
    Parses one or more p separated by op, applying op left-associatively.
    """
    def rest(x: T) -> Parsec[T]:
        return op.bind(lambda f: p.bind(lambda y: rest(f(x, y)))) | pure(x)
    return p.bind(rest)

# 17. chainr: Right-associative operator chain with a default value
def chainr(p: Parsec[T], op: Parsec[Callable[[T, T], T]], x: T) -> Parsec[T]:
    """
    Parses zero or more p separated by op, applying op right-associatively; returns x if none parsed.
    """
    return chainr1(p, op) | pure(x)

# 18. chainr1: Right-associative operator chain
def chainr1(p: Parsec[T], op: Parsec[Callable[[T, T], T]]) -> Parsec[T]:
    """
    Parses one or more p separated by op, applying op right-associatively.
    """
    def scan() -> Parsec[T]:
        return p.bind(lambda x: rest(x))
    def rest(x: T) -> Parsec[T]:
        return op.bind(lambda f: scan().bind(lambda y: pure(f(x, y)))) | pure(x)
    return scan()

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
    # Attempt p; if it succeeds, not_followed_by fails.
    # If p fails, not_followed_by succeeds.
    # Crucially, not_followed_by should not consume input.
    attempt_p_then_fail = try_parse(p).bind(
        lambda x: fail(f"unexpected {x}") # If p succeeded, this branch is taken, then fail creates an empty error
    )
    succeed_empty = pure(None) # If p failed (handled by try_parse), this branch is taken by <|>

    return attempt_p_then_fail | succeed_empty

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
def look_ahead(p: Parsec[T]) -> Parsec[T]:
    return look_ahead(p)

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

