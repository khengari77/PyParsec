"""Primitive parsers and the core ``run_parser`` entry point.

This module provides the building blocks for all other parsers:

- :func:`pure` / :func:`fail` -- trivial success and failure
- :func:`token` -- match a single input element
- :func:`try_parse` / :func:`look_ahead` -- backtracking and lookahead
- :func:`many` / :func:`many1` / :func:`skip_many` -- repetition
- :func:`tokens` / :func:`tokens_prime` -- multi-token matching
- :func:`run_parser` / :func:`parse_test` -- running parsers on input
- :func:`lazy` -- deferred parser construction for recursion
"""
from collections.abc import Sequence
from typing import Any, Callable, Optional, TypeVar, Union, cast, overload

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
    """Return a parser that succeeds with *value* without consuming input.

    Args:
        value: The value to inject into the parser pipeline.

    Returns:
        A :class:`~pyparsec.Parsec.Parsec` that always succeeds with *value*.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Prim import pure
        >>> run_parser(pure(42), "")[0]
        42
    """

    def parse(state: State) -> ParseResult[T]:
        return ParseResult.ok_empty(value, state, ParseError.new_unknown(state.pos))

    return Parsec(parse)


def fail(msg: str) -> Parsec[Any]:
    """Return a parser that always fails with the given message.

    Args:
        msg: The error message to report.

    Returns:
        A :class:`~pyparsec.Parsec.Parsec` that always fails without consuming input.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Prim import fail
        >>> _, err = run_parser(fail("oops"), "abc")
        >>> "oops" in str(err)
        True
    """

    def parse(state: State) -> ParseResult[Any]:
        return ParseResult.error_empty(ParseError.new_message(state.pos, MessageType.MESSAGE, msg))

    return Parsec(parse)


def token(
    show_tok: Callable[[S], str],
    test_tok: Callable[[S], Optional[T]],
    next_pos: Optional[Callable[[SourcePos, S], SourcePos]] = None,
) -> Parsec[T]:
    """Parse a single token from the input stream.

    This is the most fundamental parser. It examines the next input element
    and either accepts or rejects it.

    Args:
        show_tok: A function that converts a token to a display string for errors.
        test_tok: A function that returns the result value on match, or ``None`` to
            reject the token.
        next_pos: Optional function to compute the new position from a token.
            Falls back to :func:`~pyparsec.Parsec.update_pos_char` if not provided.

    Returns:
        A parser that consumes one token on success.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Prim import token
        >>> digit = token(str, lambda c: int(c) if c.isdigit() else None)
        >>> run_parser(digit, "7abc")[0]
        7
    """

    def parse(state: State) -> ParseResult[T]:
        if state.index >= len(state.input):
            return ParseResult.error_empty(
                ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, "")
            )

        tok_val = state.input[state.index]
        result_val = test_tok(tok_val)

        if result_val is None:
            return ParseResult.error_empty(
                ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, show_tok(tok_val))
            )

        # Calculate new position
        if next_pos:
            new_pos_val = next_pos(state.pos, tok_val)
        else:
            new_pos_val = update_pos_char(state.pos, str(tok_val))

        new_state = State(state.input, new_pos_val, state.user, state.index + 1)
        return ParseResult.ok_consumed(result_val, new_state, ParseError.new_unknown(new_pos_val))

    return Parsec(parse)


def try_parse(parser: Parsec[T]) -> Parsec[T]:
    """Try a parser, converting a consumed error into an empty error (backtracking).

    If *parser* fails after consuming input, ``try_parse`` resets the consumed
    flag so that alternatives (via ``|``) can still be tried.

    Args:
        parser: The parser to attempt.

    Returns:
        A backtracking version of *parser*.

    Example::

        >>> from pyparsec import run_parser, string
        >>> from pyparsec.Prim import try_parse
        >>> p = try_parse(string("abc")) | string("abd")
        >>> run_parser(p, "abd")[0]
        'abd'
    """

    def parse(state: State) -> ParseResult[T]:
        res = parser(state)

        # If parser failed AND consumed input
        if isinstance(res.reply, Error) and res.consumed:
            # Return Error with consumed=False
            return ParseResult(res.reply, False)

        return res

    return Parsec(parse)


def look_ahead(parser: Parsec[T]) -> Parsec[T]:
    """Run *parser* and return its result, but do not consume any input.

    If *parser* succeeds, the state is rolled back. If it fails, the error
    is propagated as-is.

    Args:
        parser: The parser to preview.

    Returns:
        A non-consuming version of *parser*.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Prim import look_ahead
        >>> p = look_ahead(char('a'))
        >>> val, _ = run_parser(p, "abc")
        >>> val
        'a'
    """

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


def many(p: Parsec[T]) -> Parsec[list[T]]:
    """Apply *p* zero or more times and collect the results into a list.

    Stops when *p* fails without consuming input.

    Args:
        p: The parser to repeat.

    Returns:
        A parser yielding a (possibly empty) list of results.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Prim import many
        >>> run_parser(many(char('a')), "aaab")[0]
        ['a', 'a', 'a']
    """

    def _acc(item: T, lst: list[T]) -> list[T]:
        lst.append(item)
        return lst

    return _many_accum(_acc, p, [])


def many1(p: Parsec[T]) -> Parsec[list[T]]:
    """Apply *p* one or more times and collect the results into a list.

    Fails if *p* does not succeed at least once.

    Args:
        p: The parser to repeat.

    Returns:
        A parser yielding a non-empty list of results.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Prim import many1
        >>> run_parser(many1(char('a')), "aab")[0]
        ['a', 'a']
    """

    def _acc(item: T, lst: list[T]) -> list[T]:
        lst.append(item)
        return lst

    return p.bind(lambda x: _many_accum(_acc, p, [x]))


def skip_many(p: Parsec[Any]) -> Parsec[None]:
    """Apply *p* zero or more times, discarding all results.

    Args:
        p: The parser to repeat and discard.

    Returns:
        A parser that always yields ``None``.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import space
        >>> from pyparsec.Prim import skip_many
        >>> run_parser(skip_many(space()), "   hello")[0] is None
        True
    """
    return _many_accum(lambda _, __: None, p, None)


@overload
def run_parser(
    parser: "Parsec[T]",
    input_data: Union[str, Sequence[Any]],
    user_state: Any = ...,
    source_name: str = ...,
) -> tuple[T, None]: ...


@overload
def run_parser(
    parser: "Parsec[T]",
    input_data: Union[str, Sequence[Any]],
    user_state: Any = ...,
    source_name: str = ...,
) -> tuple[None, "ParseError"]: ...


def run_parser(
    parser: Parsec[T],
    input_data: Union[str, Sequence[Any]],
    user_state: Any = None,
    source_name: str = "",
) -> tuple[Optional[T], Optional[ParseError]]:
    """Run *parser* on *input_data* and return ``(value, error)``.

    Exactly one of the two tuple elements will be ``None``.

    Args:
        parser: The parser to execute.
        input_data: The input string or sequence to parse.
        user_state: Optional user-defined state threaded through parsing.
        source_name: Optional source name for error messages (e.g. a filename).

    Returns:
        A tuple ``(value, None)`` on success, or ``(None, error)`` on failure.

    Example::

        >>> from pyparsec import run_parser, char
        >>> run_parser(char('a'), "abc")
        ('a', None)
        >>> run_parser(char('a'), "xyz")
        (None, ...)
    """
    initial_state = State(input_data, SourcePos(1, 1, source_name), user_state, 0)
    res = parser(initial_state)

    if isinstance(res.reply, Ok):
        return res.reply.value, None
    else:
        return None, res.reply.error


def parse_test(parser: Parsec[T], input_data: Union[str, Sequence[Any]]) -> None:
    """Run *parser* on *input_data* and print the result or error to stdout.

    A convenience function for interactive testing and REPL use.

    Args:
        parser: The parser to execute.
        input_data: The input string or sequence to parse.

    Example::

        >>> from pyparsec.Prim import parse_test
        >>> from pyparsec.Char import char
        >>> parse_test(char('a'), "abc")
        a
    """
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
    """Parse a specific sequence of tokens from the input.

    This is the multi-token counterpart of :func:`token`. It matches an
    exact sequence and consumes it atomically.

    Args:
        show_tokens_fn: A function to render the expected tokens as a string for errors.
        next_pos_fn: A function to compute the new position after matching.
        to_match: The sequence of tokens to match.

    Returns:
        A parser that matches *to_match* exactly and returns it.
    """

    def parse(state: State) -> ParseResult[Sequence[S]]:
        input_stream = state.input
        idx = state.index
        len_target = len(to_match)

        # 1. Text Optimization (str or bytes)
        if isinstance(input_stream, (str, bytes)):
            target: Any = to_match
            # Ensure type compatibility
            if isinstance(to_match, list):
                if isinstance(input_stream, str):
                    target = "".join(cast(list[str], to_match))
                elif isinstance(input_stream, bytes):
                    target = bytes(cast(list[bytes], to_match))

            if input_stream.startswith(target, idx):
                matched = target
                # Use optimized update_string if it's text
                if isinstance(input_stream, str):
                    new_pos = update_pos_string(state.pos, cast(str, matched))
                else:
                    new_pos = next_pos_fn(state.pos, matched)

                new_state = State(input_stream, new_pos, state.user, idx + len(matched))
                return ParseResult.ok_consumed(matched, new_state, ParseError.new_unknown(new_pos))

        # 2. Generic Sequence (List comparison)
        else:
            if len(input_stream) - idx >= len_target:
                potential_match = input_stream[idx : idx + len_target]
                if potential_match == to_match:
                    new_pos = next_pos_fn(state.pos, potential_match)
                    new_state = State(input_stream, new_pos, state.user, idx + len_target)
                    return ParseResult.ok_consumed(
                        potential_match, new_state, ParseError.new_unknown(new_pos)
                    )

        # 3. Failure
        expected_msg = show_tokens_fn(to_match)
        actual_found = input_stream[idx : idx + len_target]
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
    """Match a token sequence without consuming input on success (lookahead).

    Like :func:`tokens`, but wraps the match in :func:`look_ahead` so the
    input position is not advanced on success.

    Args:
        show_tokens_fn: A function to render expected tokens for error messages.
        _next_pos_fn: Position update function (passed through but unused on success).
        to_match: The sequence of tokens to match.

    Returns:
        A non-consuming parser that matches *to_match*.
    """
    # This is effectively look_ahead(tokens(...)) but optimized to not calc new pos
    p = tokens(show_tokens_fn, _next_pos_fn, to_match)
    return look_ahead(p)


def take_while(predicate: Callable[[str], bool]) -> Parsec[str]:
    """Scan zero or more characters matching *predicate* and return the matched string.

    Operates in bulk — no per-character parser overhead. Creates exactly one
    State and one ParseResult regardless of how many characters matched.

    Args:
        predicate: A function that returns ``True`` for characters to consume.

    Returns:
        A parser yielding the matched substring (possibly empty).
    """

    def parse(state: State) -> ParseResult[str]:
        inp = state.input
        idx = state.index
        length = len(inp)
        end = idx
        while end < length and predicate(inp[end]):
            end += 1
        if end == idx:
            return ParseResult.ok_empty("", state, ParseError.new_unknown(state.pos))
        matched = inp[idx:end]
        new_pos = update_pos_string(state.pos, matched)
        new_state = State(inp, new_pos, state.user, end)
        return ParseResult.ok_consumed(matched, new_state, ParseError.new_unknown(new_pos))

    return Parsec(parse)


def take_while1(predicate: Callable[[str], bool]) -> Parsec[str]:
    """Scan one or more characters matching *predicate* and return the matched string.

    Like :func:`take_while` but fails if no characters match.

    Args:
        predicate: A function that returns ``True`` for characters to consume.

    Returns:
        A parser yielding the non-empty matched substring.
    """

    def parse(state: State) -> ParseResult[str]:
        inp = state.input
        idx = state.index
        length = len(inp)
        end = idx
        while end < length and predicate(inp[end]):
            end += 1
        if end == idx:
            if idx >= length:
                return ParseResult.error_empty(
                    ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, "")
                )
            return ParseResult.error_empty(
                ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, repr(inp[idx]))
            )
        matched = inp[idx:end]
        new_pos = update_pos_string(state.pos, matched)
        new_state = State(inp, new_pos, state.user, end)
        return ParseResult.ok_consumed(matched, new_state, ParseError.new_unknown(new_pos))

    return Parsec(parse)


def skip_while(predicate: Callable[[str], bool]) -> Parsec[None]:
    """Skip zero or more characters matching *predicate*.

    Operates in bulk — no per-character parser overhead.

    Args:
        predicate: A function that returns ``True`` for characters to skip.

    Returns:
        A parser that always yields ``None``.
    """

    def parse(state: State) -> ParseResult[None]:
        inp = state.input
        idx = state.index
        length = len(inp)
        end = idx
        while end < length and predicate(inp[end]):
            end += 1
        if end == idx:
            return ParseResult.ok_empty(None, state, ParseError.new_unknown(state.pos))
        matched = inp[idx:end]
        new_pos = update_pos_string(state.pos, matched)
        new_state = State(inp, new_pos, state.user, end)
        return ParseResult.ok_consumed(None, new_state, ParseError.new_unknown(new_pos))

    return Parsec(parse)


def skip_while1(predicate: Callable[[str], bool]) -> Parsec[None]:
    """Skip one or more characters matching *predicate*.

    Like :func:`skip_while` but fails if no characters match.

    Args:
        predicate: A function that returns ``True`` for characters to skip.

    Returns:
        A parser that yields ``None``.
    """

    def parse(state: State) -> ParseResult[None]:
        inp = state.input
        idx = state.index
        length = len(inp)
        end = idx
        while end < length and predicate(inp[end]):
            end += 1
        if end == idx:
            if idx >= length:
                return ParseResult.error_empty(
                    ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, "")
                )
            return ParseResult.error_empty(
                ParseError.new_message(state.pos, MessageType.SYS_UNEXPECT, repr(inp[idx]))
            )
        matched = inp[idx:end]
        new_pos = update_pos_string(state.pos, matched)
        new_state = State(inp, new_pos, state.user, end)
        return ParseResult.ok_consumed(None, new_state, ParseError.new_unknown(new_pos))

    return Parsec(parse)


def lazy(parser_producer: Callable[[], Parsec[T]]) -> Parsec[T]:
    """Defer parser construction for recursive grammars.

    Calls *parser_producer* on first use and memoizes the result, breaking
    circular references that would otherwise cause infinite recursion.

    Args:
        parser_producer: A zero-argument callable that returns a :class:`Parsec`.

    Returns:
        A parser that lazily delegates to the produced parser.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Prim import lazy, pure
        >>> p = lazy(lambda: char('a'))
        >>> run_parser(p, "a")[0]
        'a'
    """
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
