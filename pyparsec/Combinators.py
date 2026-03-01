"""Higher-order parser combinators for sequencing, repetition, and choice.

This module provides combinators that build complex parsers from simpler ones:

- :func:`choice` / :func:`count` / :func:`between` -- sequencing and selection
- :func:`option` / :func:`option_maybe` / :func:`optional` -- optional parsing
- :func:`sep_by` / :func:`end_by` / :func:`sep_end_by` -- separated lists
- :func:`chainl1` / :func:`chainr1` -- operator chaining
- :func:`many_till` / :func:`not_followed_by` / :func:`eof` -- termination
- :func:`parser_trace` / :func:`parser_traced` -- debugging
"""
from typing import Any, Callable, List, Optional, TypeVar, Union, cast

from .Parsec import Error, MessageType, Ok, Parsec, ParseError, ParseResult, State
from .Prim import fail, look_ahead, many, many1, pure, token, try_parse

T = TypeVar("T")


def choice(parsers: List[Parsec[T]]) -> Parsec[T]:
    """Try each parser in *parsers* in order until one succeeds.

    Args:
        parsers: A list of parsers to attempt.

    Returns:
        A parser that returns the result of the first successful parser.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import choice
        >>> run_parser(choice([char('a'), char('b'), char('c')]), "b")[0]
        'b'
    """
    if not parsers:
        return fail("no alternatives")

    def parse(state: State) -> ParseResult[T]:
        # Initialize with a generic unknown error at current position
        max_error = ParseError.new_unknown(state.pos)

        for p in parsers:
            res = p(state)

            if isinstance(res.reply, Ok):
                # If a choice succeeds, we merge previous errors (failed attempts)
                # into the success result so the user knows what else was /expected.
                final_err = ParseError.merge(max_error, res.reply.error)
                if res.consumed:
                    return ParseResult.ok_consumed(res.reply.value, res.reply.state, final_err)
                else:
                    return ParseResult.ok_empty(res.reply.value, res.reply.state, final_err)

            if res.consumed:
                return res

            max_error = ParseError.merge(max_error, res.reply.error)

        return ParseResult.error_empty(max_error)

    return Parsec(parse)


def count(n: int, p: Parsec[T]) -> Parsec[List[T]]:
    """Apply *p* exactly *n* times and collect the results.

    Args:
        n: The number of times to apply *p*. If ``n <= 0``, returns ``[]``.
        p: The parser to repeat.

    Returns:
        A parser yielding a list of exactly *n* results.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import count
        >>> run_parser(count(3, char('a')), "aaab")[0]
        ['a', 'a', 'a']
    """
    if n <= 0:
        return pure([])

    def parse(state_initial: State) -> ParseResult[List[T]]:
        results = []
        current_state = state_initial
        consumed_overall = False
        last_error = ParseError.new_unknown(state_initial.pos)

        for _i in range(n):
            res_p = p(current_state)
            consumed_overall = consumed_overall or res_p.consumed

            if isinstance(res_p.reply, Error):
                if res_p.consumed:
                    return ParseResult(res_p.reply, True)
                else:
                    # Empty error during count is a failure for the whole count.
                    final_err = ParseError.merge(last_error, res_p.reply.error)
                    if consumed_overall:
                        return ParseResult.error_consumed(final_err)
                    else:
                        return ParseResult.error_empty(final_err)

            ok_reply: Ok[T] = res_p.reply
            results.append(ok_reply.value)
            current_state = ok_reply.state
            last_error = ok_reply.error  # Track ghost errors

        if consumed_overall:
            return ParseResult.ok_consumed(results, current_state, last_error)
        else:
            return ParseResult.ok_empty(results, current_state, last_error)

    return Parsec(parse)


def between(open: Parsec[Any], close: Parsec[Any], p: Parsec[T]) -> Parsec[T]:
    """Parse *open*, then *p*, then *close*, returning only the result of *p*.

    Args:
        open: The opening delimiter parser.
        close: The closing delimiter parser.
        p: The content parser.

    Returns:
        A parser yielding the result of *p*.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import between
        >>> run_parser(between(char('('), char(')'), char('x')), "(x)")[0]
        'x'
    """
    return open >> (lambda _: p.bind(lambda x: close >> (lambda _: pure(x))))


def option(x: T, p: Parsec[T]) -> Parsec[T]:
    """Try *p*; if it fails without consuming, return *x* as the default.

    Args:
        x: The default value.
        p: The parser to attempt.

    Returns:
        A parser yielding *p*'s result on success, or *x* on failure.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import option
        >>> run_parser(option('z', char('a')), "b")[0]
        'z'
    """
    return p | pure(x)


def option_maybe(p: Parsec[T]) -> Parsec[Optional[T]]:
    """Try *p*; return ``None`` if it fails without consuming.

    Args:
        p: The parser to attempt.

    Returns:
        A parser yielding *p*'s result wrapped in ``Optional``, or ``None``.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import option_maybe
        >>> run_parser(option_maybe(char('a')), "b")[0] is None
        True
    """
    return p.map(lambda x: cast(Optional[T], x)) | pure(cast(Optional[T], None))


def optional(p: Parsec[T]) -> Parsec[None]:
    """Try *p*, discarding its result. Always succeeds with ``None``.

    Args:
        p: The parser to attempt.

    Returns:
        A parser that always yields ``None``.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import optional
        >>> run_parser(optional(char('a')), "b")[0] is None
        True
    """
    return (p >> (lambda _: pure(None))) | pure(None)


def skip_many1(p: Parsec[Any]) -> Parsec[None]:
    """Apply *p* one or more times, discarding results. Fails if *p* doesn't match once.

    Args:
        p: The parser to repeat and discard.

    Returns:
        A parser that yields ``None``.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import space
        >>> from pyparsec.Combinators import skip_many1
        >>> run_parser(skip_many1(space()), "  x")[0] is None
        True
    """
    return p >> (lambda _: many(p) >> (lambda _: pure(None)))


def sep_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parse one or more occurrences of *p* separated by *sep*.

    Args:
        p: The element parser.
        sep: The separator parser (results are discarded).

    Returns:
        A parser yielding a non-empty list.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import sep_by1
        >>> run_parser(sep_by1(char('a'), char(',')), "a,a,a")[0]
        ['a', 'a', 'a']
    """
    return p.bind(lambda x: many(sep >> p).bind(lambda xs: pure([x] + xs)))


def sep_by(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parse zero or more occurrences of *p* separated by *sep*.

    Args:
        p: The element parser.
        sep: The separator parser (results are discarded).

    Returns:
        A parser yielding a (possibly empty) list.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import sep_by
        >>> run_parser(sep_by(char('a'), char(',')), "")[0]
        []
    """
    return sep_by1(p, sep) | pure([])


def end_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parse one or more occurrences of *p*, each followed by *sep*.

    Args:
        p: The element parser.
        sep: The terminator parser (results are discarded).

    Returns:
        A parser yielding a non-empty list.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import end_by1
        >>> run_parser(end_by1(char('a'), char(';')), "a;a;")[0]
        ['a', 'a']
    """
    return many1(p < sep)


def end_by(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parse zero or more occurrences of *p*, each followed by *sep*.

    Args:
        p: The element parser.
        sep: The terminator parser (results are discarded).

    Returns:
        A parser yielding a (possibly empty) list.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import end_by
        >>> run_parser(end_by(char('a'), char(';')), "")[0]
        []
    """
    return many(p < sep)


def sep_end_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parse one or more occurrences of *p*, separated and optionally ended by *sep*.

    Args:
        p: The element parser.
        sep: The separator/terminator parser (results are discarded).

    Returns:
        A parser yielding a non-empty list.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import sep_end_by1
        >>> run_parser(sep_end_by1(char('a'), char(';')), "a;a;")[0]
        ['a', 'a']
    """

    def parse(state: State) -> ParseResult[List[T]]:
        res_p = p(state)
        if isinstance(res_p.reply, Error):
            return ParseResult(Error(res_p.reply.error), res_p.consumed)

        ok_reply: Ok[T] = res_p.reply
        results = [ok_reply.value]
        current_state = ok_reply.state
        overall_consumed = res_p.consumed
        last_err = ok_reply.error

        while True:
            res_sep = sep(current_state)

            if isinstance(res_sep.reply, Error):
                if res_sep.consumed:
                    return ParseResult(res_sep.reply, True)

                final_err = ParseError.merge(last_err, res_sep.reply.error)
                return (
                    ParseResult.ok_consumed(results, current_state, final_err)
                    if overall_consumed
                    else ParseResult.ok_empty(results, current_state, final_err)
                )

            sep_ok: Ok = res_sep.reply
            state_after_sep = sep_ok.state
            consumed_sep = res_sep.consumed

            res_next_p = p(state_after_sep)

            if isinstance(res_next_p.reply, Error):
                if res_next_p.consumed:
                    return ParseResult(res_next_p.reply, True)

                final_err = ParseError.merge(sep_ok.error, res_next_p.reply.error)
                overall_consumed = overall_consumed or consumed_sep
                return (
                    ParseResult.ok_consumed(results, state_after_sep, final_err)
                    if overall_consumed
                    else ParseResult.ok_empty(results, state_after_sep, final_err)
                )

            p_ok: Ok[T] = res_next_p.reply
            results.append(p_ok.value)
            current_state = p_ok.state
            overall_consumed = overall_consumed or consumed_sep or res_next_p.consumed
            last_err = p_ok.error

    return Parsec(parse)


def sep_end_by(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parse zero or more occurrences of *p*, separated and optionally ended by *sep*.

    Args:
        p: The element parser.
        sep: The separator/terminator parser (results are discarded).

    Returns:
        A parser yielding a (possibly empty) list.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import sep_end_by
        >>> run_parser(sep_end_by(char('a'), char(';')), "")[0]
        []
    """
    return sep_end_by1(p, sep) | pure([])


def chainl1(p: Parsec[T], op: Parsec[Callable[[T, T], T]]) -> Parsec[T]:
    """Parse one or more *p* separated by *op*, applying *op* left-associatively.

    Args:
        p: The operand parser.
        op: The operator parser, returning a binary function.

    Returns:
        A parser yielding the left-folded result.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Char import digit
        >>> from pyparsec.Combinators import chainl1
        >>> num = digit().map(int)
        >>> add = char('+').map(lambda _: lambda a, b: a + b)
        >>> run_parser(chainl1(num, add), "1+2+3")[0]
        6
    """

    def parse(state: State) -> ParseResult[T]:
        res_p = p(state)
        if isinstance(res_p.reply, Error):
            return res_p

        ok_p: Ok[T] = res_p.reply
        acc = ok_p.value
        curr_state = ok_p.state
        consumed = res_p.consumed
        err = ok_p.error

        while True:
            res_op = op(curr_state)
            if isinstance(res_op.reply, Error):
                if res_op.consumed:
                    return ParseResult(res_op.reply, True)
                # Empty error on op -> End of chain
                final_err = ParseError.merge(err, res_op.reply.error)
                return (
                    ParseResult.ok_consumed(acc, curr_state, final_err)
                    if consumed
                    else ParseResult.ok_empty(acc, curr_state, final_err)
                )

            ok_op = res_op.reply
            op_func = ok_op.value

            res_right = p(ok_op.state)
            if isinstance(res_right.reply, Error):
                # Op succeeded, right failed
                final_consumed = consumed or res_op.consumed or res_right.consumed
                merged_err = ParseError.merge(ok_op.error, res_right.reply.error)

                if res_right.consumed:
                    return ParseResult(res_right.reply, True)
                else:
                    # Op succeeded but right failed empty. This is a fatal error for chainl1
                    # because we parsed an operator, so we MUST find a right-hand side.
                    return ParseResult(Error(merged_err), final_consumed)

            ok_right = res_right.reply
            acc = op_func(acc, ok_right.value)
            curr_state = ok_right.state
            consumed = consumed or res_op.consumed or res_right.consumed
            err = ok_right.error

    return Parsec(parse)


def chainl(p: Parsec[T], op: Parsec[Callable[[T, T], T]], x: T) -> Parsec[T]:
    """Parse zero or more *p* separated by *op* left-associatively, defaulting to *x*.

    Like :func:`chainl1` but returns *x* if *p* never matches.

    Args:
        p: The operand parser.
        op: The operator parser, returning a binary function.
        x: The default value when *p* never matches.

    Returns:
        A parser yielding the left-folded result, or *x*.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import chainl
        >>> run_parser(chainl(char('a'), char('+').map(lambda _: lambda a, b: a + b), 'z'), "")[0]
        'z'
    """
    return chainl1(p, op) | pure(x)


def chainr1(p: Parsec[T], op: Parsec[Callable[[T, T], T]]) -> Parsec[T]:
    """Parse one or more *p* separated by *op*, applying *op* right-associatively.

    Args:
        p: The operand parser.
        op: The operator parser, returning a binary function.

    Returns:
        A parser yielding the right-folded result.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Char import digit
        >>> from pyparsec.Combinators import chainr1
        >>> num = digit().map(int)
        >>> exp = char('^').map(lambda _: lambda a, b: a ** b)
        >>> run_parser(chainr1(num, exp), "2^3^2")[0]
        512
    """

    def apply_right_associative(scan_results_val: List[Union[T, Callable[[T, T], T]]]) -> T:
        if not scan_results_val:
            raise ValueError("Empty chain")

        acc = cast(T, scan_results_val[-1])
        for i in range(len(scan_results_val) - 2, -1, -2):
            op_func = cast(Callable[[T, T], T], scan_results_val[i])
            left_val = cast(T, scan_results_val[i - 1])
            acc = op_func(left_val, acc)

        return acc

    return _scan_op_chain(p, op).map(apply_right_associative)


def chainr(p: Parsec[T], op: Parsec[Callable[[T, T], T]], x: T) -> Parsec[T]:
    """Parse zero or more *p* separated by *op* right-associatively, defaulting to *x*.

    Like :func:`chainr1` but returns *x* if *p* never matches.

    Args:
        p: The operand parser.
        op: The operator parser, returning a binary function.
        x: The default value when *p* never matches.

    Returns:
        A parser yielding the right-folded result, or *x*.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Combinators import chainr
        >>> run_parser(chainr(char('a'), char('+').map(lambda _: lambda a, b: a + b), 'z'), "")[0]
        'z'
    """
    return chainr1(p, op) | pure(x)


def _scan_op_chain(
    term_parser: Parsec[T], op_parser: Parsec[Callable[[T, T], T]]
) -> Parsec[List[Union[T, Callable[[T, T], T]]]]:
    """Helper for chainr1: parses x (op x)* into a flat list."""

    def parse(state: State) -> ParseResult[List[Union[T, Any]]]:
        res_first = term_parser(state)
        if isinstance(res_first.reply, Error):
            return ParseResult(Error(res_first.reply.error), res_first.consumed)

        ok_first: Ok[T] = res_first.reply
        results: List[Union[T, Any]] = [ok_first.value]
        curr_state = ok_first.state
        consumed = res_first.consumed
        err = ok_first.error

        while True:
            res_op = op_parser(curr_state)
            if isinstance(res_op.reply, Error):
                if res_op.consumed:
                    return ParseResult(res_op.reply, True)
                # Done
                final_err = ParseError.merge(err, res_op.reply.error)
                return (
                    ParseResult.ok_consumed(results, curr_state, final_err)
                    if consumed
                    else ParseResult.ok_empty(results, curr_state, final_err)
                )

            ok_op = res_op.reply
            res_next = term_parser(ok_op.state)

            if isinstance(res_next.reply, Error):
                final_consumed = consumed or res_op.consumed or res_next.consumed
                merged_err = ParseError.merge(ok_op.error, res_next.reply.error)
                if res_next.consumed:
                    return ParseResult(res_next.reply, True)
                else:
                    # Missing RHS after Op -> Fail
                    return ParseResult(Error(merged_err), final_consumed)

            ok_next: Ok[T] = res_next.reply
            results.append(ok_op.value)
            results.append(ok_next.value)

            curr_state = ok_next.state
            consumed = consumed or res_op.consumed or res_next.consumed
            err = ok_next.error

    return Parsec(parse)


def any_token() -> Parsec[str]:
    """Parse any single token from the input stream.

    Returns:
        A parser that consumes and returns any token.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Combinators import any_token
        >>> run_parser(any_token(), "hello")[0]
        'h'
    """
    return token(lambda t: str(t), lambda t: t)


def not_followed_by(p: Parsec[Any]) -> Parsec[None]:
    """Succeed only if *p* fails. Never consumes input.

    Args:
        p: The parser that must *not* match.

    Returns:
        A parser that yields ``None`` when *p* fails.

    Example::

        >>> from pyparsec import run_parser, char, string
        >>> from pyparsec.Combinators import not_followed_by
        >>> p = string("let") < not_followed_by(char('t'))
        >>> run_parser(p, "let ")[0]
        'let'
    """

    def parse(state: State) -> ParseResult[None]:
        res = try_parse(look_ahead(p))(state)
        if isinstance(res.reply, Error):
            return ParseResult.ok_empty(None, state, ParseError.new_unknown(state.pos))
        else:
            val_str = str(res.reply.value)
            err = ParseError.new_message(state.pos, MessageType.UNEXPECT, val_str)
            return ParseResult.error_empty(err)

    return Parsec(parse)


def eof() -> Parsec[None]:
    """Succeed only at the end of input.

    Returns:
        A parser that yields ``None`` at end of input, or fails otherwise.

    Example::

        >>> from pyparsec import run_parser, string
        >>> from pyparsec.Combinators import eof
        >>> run_parser(string("hi") > eof(), "hi")[0] is None
        True
    """
    return not_followed_by(any_token()).label("end of input")


def many_till(p: Parsec[T], end: Parsec[Any]) -> Parsec[List[T]]:
    """Apply *p* zero or more times until *end* succeeds, collecting the results.

    The *end* parser is consumed on success. The results of *p* are
    collected into a list; the result of *end* is discarded.

    Args:
        p: The element parser.
        end: The terminator parser.

    Returns:
        A parser yielding a list of *p* results.

    Example::

        >>> from pyparsec import run_parser, char
        >>> from pyparsec.Char import any_char
        >>> from pyparsec.Combinators import many_till
        >>> run_parser(many_till(any_char(), char('.')), "abc.")[0]
        ['a', 'b', 'c']
    """

    def scan(state: State) -> ParseResult[List[T]]:
        results: list[T] = []
        curr = state
        consumed = False
        err = ParseError.new_unknown(state.pos)

        while True:
            res_end = end(curr)
            if isinstance(res_end.reply, Ok):
                consumed = consumed or res_end.consumed
                final_err = ParseError.merge(err, res_end.reply.error)
                return (
                    ParseResult.ok_consumed(results, res_end.reply.state, final_err)
                    if consumed
                    else ParseResult.ok_empty(results, res_end.reply.state, final_err)
                )

            if res_end.consumed:
                return ParseResult(res_end.reply, True)

            err = ParseError.merge(err, res_end.reply.error)
            res_p = p(curr)

            if isinstance(res_p.reply, Error):
                if res_p.consumed:
                    return ParseResult(res_p.reply, True)
                # Both failed empty
                return ParseResult(Error(ParseError.merge(err, res_p.reply.error)), consumed)

            ok_p: Ok[T] = res_p.reply
            results.append(ok_p.value)
            curr = ok_p.state
            consumed = consumed or res_p.consumed
            err = ok_p.error

    return Parsec(scan)


def parser_trace(label_str: str) -> Parsec[None]:
    """Insert a trace point that prints the current parse position to stdout.

    Useful for debugging. Does not consume input.

    Args:
        label_str: A label to prefix the trace output.

    Returns:
        A parser that prints a trace line and yields ``None``.

    Example::

        >>> from pyparsec.Combinators import parser_trace
        >>> # parser_trace("here")(state) prints: here: "..." at (line 1, column 1)
    """

    def parse(state: State) -> ParseResult[None]:
        input_preview = str(state.input[state.index:])[:30]
        print(f'{label_str}: "{input_preview}" at {state.pos}')
        return ParseResult.ok_empty(None, state, ParseError.new_unknown(state.pos))

    return Parsec(parse)


def parser_traced(label_str: str, p: Parsec[T]) -> Parsec[T]:
    """Wrap *p* with trace output showing entry and backtrack events.

    Prints the input preview before running *p* and a backtrack message
    if *p* fails without consuming input.

    Args:
        label_str: A label to prefix the trace output.
        p: The parser to trace.

    Returns:
        A traced version of *p*.

    Example::

        >>> from pyparsec.Combinators import parser_traced
        >>> from pyparsec.Char import char
        >>> # parser_traced("letter", char('a')) prints trace info when run
    """

    def parse(state: State) -> ParseResult[T]:
        parser_trace(label_str)(state)
        res = p(state)
        if isinstance(res.reply, Ok):
            return res
        # If failed
        if not res.consumed:
            print(f"{label_str} backtracked")
        return res

    return Parsec(parse)
