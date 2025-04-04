from typing import List, Optional, Callable, Any, TypeVar
from .Parsec import Parsec, State, ParseError, SourcePos, Result
from .Prim import pure, fail, try_parse, token, many, look_ahead

T = TypeVar('T')  # Generic type for parser results

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
    """
    Parses exactly n occurrences of parser p, returning a list of results.
    Returns an empty list if n <= 0.
    """
    if n <= 0:
        return pure([])
    def parse(state: State) -> Result[List[T]]:
        results = []
        current_state = state
        for _ in range(n):
            value, new_state, err = p(current_state)
            if err or value is None:
                return None, state, err or ParseError(current_state.pos, "count failed")
            results.append(value)
            current_state = new_state
        return results, current_state, None
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

# 8. many1: Parses one or more occurrences of a parser
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
    return sep_end_by1(p, sep) | pure([])

# 14. sepEndBy1: Parses one or more occurrences separated and optionally ended by a separator
def sep_end_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """
    Parses one or more occurrences of p separated and optionally ended by sep.
    """
    def parse(state: State) -> Result[List[T]]:
        value, new_state, err = p(state)
        if err or value is None:
            return None, state, err or ParseError(state.pos, "sepEndBy1 failed")
        sep_value, sep_state, sep_err = sep(new_state)
        if not sep_err and sep_value is not None:
            rest_value, rest_state, rest_err = sep_end_by(p, sep)(sep_state)
            if not rest_err and rest_value is not None:
                return [value] + rest_value, rest_state, None
        return [value], new_state, None
    return Parsec(parse)

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
    return token(lambda t: str(t), lambda t: t)  # Assumes token is from previous implementation

# 21. notFollowedBy: Succeeds if a parser fails without consuming input
def not_followed_by(p: Parsec[Any]) -> Parsec[None]:
    """
    Succeeds if parser p fails without consuming input, does not consume input itself.
    """
    def parse(state: State) -> Result[None]:
        value, new_state, err = try_parse(p)(state)
        if value is not None and not err:
            return None, state, ParseError(state.pos, f"unexpected {value}")
        return None, state, None
    return try_parse(parse)

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
def parser_trace(label: str) -> Parsec[None]:
    """
    Prints the remaining input with a label for debugging, does not consume input.
    """
    def parse(state: State) -> Result[None]:
        print(f"{label}: \"{state.input}\"")
        return None, state, None
    return Parsec(parse)

# 25. parserTraced: Debugging parser that traces execution and backtracking
def parser_traced(label: str, p: Parsec[T]) -> Parsec[T]:
    """
    Prints the state with a label, applies p, and indicates backtracking if p fails.
    """
    def backtrack_parser(state: State) -> Result[T]:
        print(f"{label} backtracked")
        return None, state, ParseError(state.pos, label)
    
    def parse(state: State) -> Result[T]:
        # Run parser_trace manually without binding its result
        _, trace_state, trace_err = parser_trace(label)(state)
        if trace_err:
            return None, trace_state, trace_err
        # Run p | backtrack_parser on the same state
        return (p | Parsec(backtrack_parser))(trace_state)
    
    return Parsec(parse)
