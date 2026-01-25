from typing import List, Optional, Callable, Any, TypeVar, Union
from .Parsec import Parsec, State, ParseError, ParseResult, MessageType, Reply, Ok, Error
from .Prim import pure, fail, try_parse, token, many, many1, look_ahead

T = TypeVar('T')

def choice(parsers: List[Parsec[T]]) -> Parsec[T]:
    """
    Applies a list of parsers in order until one succeeds.
    Returns the value of the succeeding parser, or fails if none succeed.
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
                # into the success result so the user knows what else was expected.
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
    if n <= 0:
        return pure([])
    
    def parse(state_initial: State) -> ParseResult[List[T]]:
        results = []
        current_state = state_initial
        consumed_overall = False
        last_error = ParseError.new_unknown(state_initial.pos)

        for i in range(n):
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
            last_error = ok_reply.error # Track ghost errors

        if consumed_overall:
            return ParseResult.ok_consumed(results, current_state, last_error)
        else:
            return ParseResult.ok_empty(results, current_state, last_error)
    return Parsec(parse)

def between(open: Parsec[Any], close: Parsec[Any], p: Parsec[T]) -> Parsec[T]:
    return open >> (lambda _: p.bind(lambda x: close >> (lambda _: pure(x))))

def option(x: T, p: Parsec[T]) -> Parsec[T]:
    return p | pure(x)

def option_maybe(p: Parsec[T]) -> Parsec[Optional[T]]:
    return p | pure(None)

def optional(p: Parsec[T]) -> Parsec[None]:
    return (p >> (lambda _: pure(None))) | pure(None)

def skip_many1(p: Parsec[Any]) -> Parsec[None]:
    return p >> (lambda _: many(p) >> (lambda _: pure(None)))

def sep_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parses one or more occurrences of p separated by sep."""
    return p.bind(lambda x: many(sep >> p).bind(lambda xs: pure([x] + xs)))

def sep_by(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parses zero or more occurrences of p separated by sep."""
    return sep_by1(p, sep) | pure([])

def end_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parses one or more occurrences of p, each followed by sep."""
    return many1(p < sep)

def end_by(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parses zero or more occurrences of p, each followed by sep."""
    return many(p < sep)

def sep_end_by1(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    """Parses one or more occurrences of p, separated and optionally ended by sep."""
    def parse(state: State) -> ParseResult[List[T]]:
        res_p = p(state)
        if isinstance(res_p.reply, Error):
            return res_p 
        
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
                return ParseResult.ok_consumed(results, current_state, final_err) if overall_consumed \
                       else ParseResult.ok_empty(results, current_state, final_err)
            
            sep_ok: Ok = res_sep.reply
            state_after_sep = sep_ok.state
            consumed_sep = res_sep.consumed
            
            res_next_p = p(state_after_sep)
            
            if isinstance(res_next_p.reply, Error):
                if res_next_p.consumed:
                    return ParseResult(res_next_p.reply, True)
                
                final_err = ParseError.merge(sep_ok.error, res_next_p.reply.error)
                overall_consumed = overall_consumed or consumed_sep
                return ParseResult.ok_consumed(results, state_after_sep, final_err) if overall_consumed \
                       else ParseResult.ok_empty(results, state_after_sep, final_err)

            p_ok: Ok[T] = res_next_p.reply
            results.append(p_ok.value)
            current_state = p_ok.state
            overall_consumed = overall_consumed or consumed_sep or res_next_p.consumed
            last_err = p_ok.error
            
    return Parsec(parse)

def sep_end_by(p: Parsec[T], sep: Parsec[Any]) -> Parsec[List[T]]:
    return sep_end_by1(p, sep) | pure([])

def chainl1(p: Parsec[T], op: Parsec[Callable[[T, T], T]]) -> Parsec[T]:
    """Parses one or more p separated by op, applying op left-associatively."""
    def parse(state: State) -> ParseResult[T]:
        res_p = p(state)
        if isinstance(res_p.reply, Error): return res_p
        
        ok_p: Ok[T] = res_p.reply
        acc = ok_p.value
        curr_state = ok_p.state
        consumed = res_p.consumed
        err = ok_p.error

        while True:
            res_op = op(curr_state)
            if isinstance(res_op.reply, Error):
                if res_op.consumed: return ParseResult(res_op.reply, True)
                # Empty error on op -> End of chain
                final_err = ParseError.merge(err, res_op.reply.error)
                return ParseResult.ok_consumed(acc, curr_state, final_err) if consumed \
                       else ParseResult.ok_empty(acc, curr_state, final_err)
            
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
    return chainl1(p, op) | pure(x)

def chainr1(p: Parsec[T], op: Parsec[Callable[[T, T], T]]) -> Parsec[T]:
    """
    Parses one or more p separated by op, applying op right-associatively.
    Uses _scan_op_chain to get a list [x1, f1, x2, f2, x3] then folds right.
    """
    def apply_right_associative(scan_results_val: List[Union[T, Callable[[T, T], T]]]) -> T:
        if not scan_results_val: raise ValueError("Empty chain")
        
        acc = scan_results_val[-1]
        for i in range(len(scan_results_val) - 2, -1, -2):
            op_func = scan_results_val[i]
            left_val = scan_results_val[i-1]
            acc = op_func(left_val, acc)
            
        return acc

    return _scan_op_chain(p, op).map(apply_right_associative)

def chainr(p: Parsec[T], op: Parsec[Callable[[T, T], T]], x: T) -> Parsec[T]:
    return chainr1(p, op) | pure(x)

def _scan_op_chain(
    term_parser: Parsec[T],
    op_parser: Parsec[Callable[[T, T], T]] 
) -> Parsec[List[Union[T, Callable[[T, T], T]]]]:
    """Helper for chainr1: parses x (op x)* into a flat list."""
    def parse(state: State) -> ParseResult[List[Union[T, Any]]]:
        res_first = term_parser(state)
        if isinstance(res_first.reply, Error): return res_first
        
        ok_first: Ok[T] = res_first.reply
        results: List[Union[T, Any]] = [ok_first.value]
        curr_state = ok_first.state
        consumed = res_first.consumed
        err = ok_first.error
        
        while True:
            res_op = op_parser(curr_state)
            if isinstance(res_op.reply, Error):
                if res_op.consumed: return ParseResult(res_op.reply, True)
                # Done
                final_err = ParseError.merge(err, res_op.reply.error)
                return ParseResult.ok_consumed(results, curr_state, final_err) if consumed \
                       else ParseResult.ok_empty(results, curr_state, final_err)
            
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
    return token(lambda t: str(t), lambda t: t)

def not_followed_by(p: Parsec[Any]) -> Parsec[None]:
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
    return not_followed_by(any_token()).label("end of input")

def many_till(p: Parsec[T], end: Parsec[Any]) -> Parsec[List[T]]:
    def scan(state: State) -> ParseResult[List[T]]:
        results = []
        curr = state
        consumed = False
        err = ParseError.new_unknown(state.pos)
        
        while True:
            res_end = end(curr)
            if isinstance(res_end.reply, Ok):
                consumed = consumed or res_end.consumed
                final_err = ParseError.merge(err, res_end.reply.error)
                return ParseResult.ok_consumed(results, res_end.reply.state, final_err) if consumed \
                       else ParseResult.ok_empty(results, res_end.reply.state, final_err)
            
            if res_end.consumed:
                return ParseResult(res_end.reply, True)
                
            err = ParseError.merge(err, res_end.reply.error)
            res_p = p(curr)
            
            if isinstance(res_p.reply, Error):
                if res_p.consumed: return ParseResult(res_p.reply, True)
                # Both failed empty
                return ParseResult(Error(ParseError.merge(err, res_p.reply.error)), consumed)
            
            ok_p: Ok[T] = res_p.reply
            results.append(ok_p.value)
            curr = ok_p.state
            consumed = consumed or res_p.consumed
            err = ok_p.error
            
    return Parsec(scan)

def parser_trace(label_str: str) -> Parsec[None]:
    def parse(state: State) -> ParseResult[None]:
        input_preview = str(state.input)[:30]
        print(f"{label_str}: \"{input_preview}\" at {state.pos}")
        return ParseResult.ok_empty(None, state, ParseError.new_unknown(state.pos))
    return Parsec(parse)

def parser_traced(label_str: str, p: Parsec[T]) -> Parsec[T]:
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
