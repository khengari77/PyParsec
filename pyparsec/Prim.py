from typing import Any, Callable, List, Optional, Sequence, Tuple, TypeVar, Union, overload, cast

from .Parsec import (
    Error,
    Message,
    MessageType,
    Ok,
    Parsec,
    ParseError,
    ParseResult,
    SourcePos,
    State,
    update_pos_char,
    update_pos_string,
)

# --- Type Variables ---
T = TypeVar("T")
U = TypeVar("U")
S = TypeVar("S")  # Input element type (e.g., char, int, Token)
AccType = TypeVar("AccType")  # Accumulator type for many


def pure(value: T) -> Parsec[T]:
    """Return a parser that succeeds with a value without consuming input."""

    def parse(state: State) -> ParseResult[T]:
        return ParseResult.ok_empty(value, state, ParseError.new_unknown(state.pos))

    return Parsec(parse)


def fail(msg: str) -> Parsec[Any]:
    """A parser that always fails with a message."""

    def parse(state: State) -> ParseResult[Any]:
        return ParseResult.error_empty(ParseError.new_message(state.pos, MessageType.MESSAGE, msg))

    return Parsec(parse)


def token(
    show_tok: Callable[[S], str],
    test_tok: Callable[[S], Optional[T]],
    next_pos: Optional[Callable[[SourcePos, S], SourcePos]] = None,
) -> Parsec[T]:
    """
    Parse a single token.
    next_pos is optional: if provided, it calculates new position from the token.
    If not provided, it falls back to standard text logic.
    """

    def parse(state: State) -> ParseResult[T]:
        if not state.input:  # Handles empty str, bytes, or list
            return ParseResult.error_empty(
                ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, "")
            )

        tok_val = state.input[0]
        result_val = test_tok(tok_val)

        if result_val is None:
            return ParseResult.error_empty(
                ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, show_tok(tok_val))
            )

        # Calculate new position
        if next_pos:
            new_pos_val = next_pos(state.pos, tok_val)
        else:
            # Fallback for text streams
            # We cast to str to be safe, assuming S is char-like if next_pos wasn't provided
            new_pos_val = update_pos_char(state.pos, str(tok_val))

        new_state = State(state.input[1:], new_pos_val, state.user)
        return ParseResult.ok_consumed(result_val, new_state, ParseError.new_unknown(new_pos_val))

    return Parsec(parse)


def try_parse(parser: Parsec[T]) -> Parsec[T]:
    """Try a parser, converting a consumed error into an empty error (backtracking)."""

    def parse(state: State) -> ParseResult[T]:
        res = parser(state)

        # If parser failed AND consumed input
        if isinstance(res.reply, Error) and res.consumed:
            # Return Error with consumed=False
            return ParseResult(res.reply, False)

        return res

    return Parsec(parse)


def look_ahead(parser: Parsec[T]) -> Parsec[T]:
    """Parses p, returns its result, but rolls back state. Consumes nothing."""

    def parse(state: State) -> ParseResult[T]:
        res = parser(state)

        if isinstance(res.reply, Ok):
            # Success: Return value, but ORIGINAL state. Consumed = False.
            return ParseResult.ok_empty(res.reply.value, state, ParseError.new_unknown(state.pos))
        else:
            # Error: Propagate error exactly as is (if it consumed, we consumed).
            return res

    return Parsec(parse)


def _many_accum(
    acc_func: Callable[[T, AccType], AccType], p: Parsec[T], empty_acc_value: AccType
) -> Parsec[AccType]:
    def parse_accum(state_outer: State) -> ParseResult[AccType]:
        current_acc: AccType = (
            cast(Any, empty_acc_value).copy() 
            if hasattr(empty_acc_value, "copy") 
            else empty_acc_value
        )
        accum_state: State = state_outer
        consumed_overall: bool = False
        last_err: ParseError = ParseError.new_unknown(state_outer.pos)

        while True:
            res_p = p(accum_state)

            if isinstance(res_p.reply, Error):
                if res_p.consumed:
                    return ParseResult(res_p.reply, True)
                else:
                    final_err = ParseError.merge(last_err, res_p.reply.error)
                    if consumed_overall:
                        return ParseResult.ok_consumed(current_acc, accum_state, final_err)
                    else:
                        return ParseResult.ok_empty(current_acc, accum_state, final_err)

            ok_reply: Ok[T] = res_p.reply

            if not res_p.consumed:
                return ParseResult.error_consumed(
                    ParseError.new_message(
                        accum_state.pos,
                        MessageType.MESSAGE,
                        "many: combinator applied to a parser that accepts an empty string.",
                    )
                )

            consumed_overall = True
            current_acc = acc_func(ok_reply.value, current_acc)
            accum_state = ok_reply.state
            last_err = ok_reply.error

    return Parsec(parse_accum)


def many(p: Parsec[T]) -> Parsec[List[T]]:
    def _acc(item: T, lst: List[T]) -> List[T]:
        lst.append(item)
        return lst

    return _many_accum(_acc, p, [])


def many1(p: Parsec[T]) -> Parsec[List[T]]:
    def _acc(item: T, lst: List[T]) -> List[T]:
        lst.append(item)
        return lst

    return p.bind(lambda x: _many_accum(_acc, p, [x]))


def skip_many(p: Parsec[Any]) -> Parsec[None]:
    """Skips zero or more occurrences of `p`."""
    return _many_accum(lambda _, __: None, p, None)


@overload
def run_parser(
    parser: "Parsec[T]",
    input_data: Union[str, Sequence[Any]],
    user_state: Any = ...,
    source_name: str = ...,
) -> Tuple[T, None]: ...


@overload
def run_parser(
    parser: "Parsec[T]",
    input_data: Union[str, Sequence[Any]],
    user_state: Any = ...,
    source_name: str = ...,
) -> Tuple[None, "ParseError"]: ...


def run_parser(
    parser: Parsec[T],
    input_data: Union[str, Sequence[Any]],
    user_state: Any = None,
    source_name: str = "",
) -> Tuple[Optional[T], Optional[ParseError]]:
    """Helper to run a parser and extract value/error."""
    initial_state = State(input_data, SourcePos(1, 1, source_name), user_state)
    res = parser(initial_state)

    if isinstance(res.reply, Ok):
        return res.reply.value, None
    else:
        return None, res.reply.error


def parse_test(parser: Parsec[T], input_data: Union[str, Sequence[Any]]) -> None:
    val, err = run_parser(parser, input_data)
    if err:
        print(err)
    else:
        print(val)


def tokens(
    show_tokens_fn: Callable[[Sequence[S]], str],
    next_pos_fn: Callable[[SourcePos, Sequence[S]], SourcePos],
    to_match: Sequence[S],
) -> Parsec[Sequence[S]]:
    """
    Polymorphic tokens parser.
    """

    def parse(state: State) -> ParseResult[Sequence[S]]:
        input_stream = state.input

        # 1. Text Optimization (str or bytes)
        if isinstance(input_stream, (str, bytes)):
            target: Any = to_match
            # Ensure type compatibility
            if isinstance(to_match, list):
                if isinstance(input_stream, str):
                    target = "".join(cast(List[str], to_match))
                elif isinstance(input_stream, bytes):
                    target = bytes(cast(List[bytes], to_match))

            if input_stream.startswith(target):
                matched = target
                # Use optimized update_string if it's text
                if isinstance(input_stream, str):
                    new_pos = update_pos_string(state.pos, cast(str, matched))
                else:
                    new_pos = next_pos_fn(state.pos, matched)

                new_state = State(input_stream[len(matched) :], new_pos, state.user)
                return ParseResult.ok_consumed(matched, new_state, ParseError.new_unknown(new_pos))

        # 2. Generic Sequence (List comparison)
        else:
            len_target = len(to_match)
            if len(input_stream) >= len_target:
                potential_match = input_stream[:len_target]
                if potential_match == to_match:
                    new_pos = next_pos_fn(state.pos, potential_match)
                    new_state = State(input_stream[len_target:], new_pos, state.user)
                    return ParseResult.ok_consumed(
                        potential_match, new_state, ParseError.new_unknown(new_pos)
                    )

        # 3. Failure
        expected_msg = show_tokens_fn(to_match)
        len_to_match = len(to_match)
        actual_found = input_stream[:len_to_match]
        actual_msg_text = show_tokens_fn(actual_found) if len(actual_found) > 0 else ""

        err = ParseError(
            state.pos,
            [
                Message(MessageType.EXPECT, expected_msg),
                Message(MessageType.SYS_UNEXPECT, actual_msg_text),
            ],
        )
        return ParseResult.error_empty(err)

    return Parsec(parse)


def tokens_prime(
    show_tokens_fn: Callable[[Sequence[S]], str],
    _next_pos_fn: Callable,  # Unused for prime (no consumption)
    to_match: Sequence[S],
) -> Parsec[Sequence[S]]:
    """Matches tokens like 'string', but consumes nothing on success (lookahead)."""
    # This is effectively look_ahead(tokens(...)) but optimized to not calc new pos
    p = tokens(show_tokens_fn, _next_pos_fn, to_match)
    return look_ahead(p)


def lazy(parser_producer: Callable[[], Parsec[T]]) -> Parsec[T]:
    """Lazy evaluation for recursive parsers."""
    memoized_parser: Optional[Parsec[T]] = None

    def parse(state: State) -> ParseResult[T]:
        nonlocal memoized_parser
        if memoized_parser is None:
            memoized_parser = parser_producer()
            if not isinstance(memoized_parser, Parsec):
                raise TypeError(
                    f"Lazy parser producer returned {type(memoized_parser)}, expected Parsec"
                )
        return memoized_parser(state)

    return Parsec(parse)
