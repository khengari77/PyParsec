from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Callable, TypeVar, Union
from .Parsec import Parsec
from .Combinators import choice, chainl1, chainr1
from .Prim import pure, fail

T = TypeVar('T')

class Assoc(Enum):
    NONE = auto()
    LEFT = auto()
    RIGHT = auto()

@dataclass
class Operator:
    pass

@dataclass
class Infix(Operator):
    parser: Parsec[Callable[[T, T], T]]
    assoc: Assoc

@dataclass
class Prefix(Operator):
    parser: Parsec[Callable[[T], T]]

@dataclass
class Postfix(Operator):
    parser: Parsec[Callable[[T], T]]

def build_expression_parser(table: List[List[Operator]], simple_term: Parsec[T]) -> Parsec[T]:
    term = simple_term
    for ops in table:
        term = _make_level_parser(ops, term)
    return term

def _make_level_parser(ops: List[Operator], term: Parsec[T]) -> Parsec[T]:
    infix_r = []
    infix_l = []
    infix_n = []
    prefix  = []
    postfix = []
    
    for op in ops:
        if isinstance(op, Infix):
            if op.assoc == Assoc.RIGHT: infix_r.append(op.parser)
            elif op.assoc == Assoc.LEFT: infix_l.append(op.parser)
            else: infix_n.append(op.parser)
        elif isinstance(op, Prefix):
            prefix.append(op.parser)
        elif isinstance(op, Postfix):
            postfix.append(op.parser)

    # 1. Handle Prefix and Postfix
    # Logic: P = (pre <|> id) . term . (post <|> id)
    if prefix:
        pre_parser = choice(prefix) | pure(lambda x: x)
    else:
        pre_parser = pure(lambda x: x)

    if postfix:
        post_parser = choice(postfix) | pure(lambda x: x)
    else:
        post_parser = pure(lambda x: x)

    # Construct the term parser for this level
    # We bind: f <- pre, x <- term, g <- post, return g(f(x))
    term_parser = pre_parser.bind(lambda f: 
                  term.bind(lambda x: 
                  post_parser.bind(lambda g: 
                  pure(g(f(x))))))

    # 2. Handle Infix
    result_parser = term_parser
    
    if infix_l:
        op_l = choice(infix_l)
        result_parser = chainl1(result_parser, op_l)
        
    if infix_r:
        op_r = choice(infix_r)
        result_parser = chainr1(result_parser, op_r)
        
    if infix_n:
        op_n = choice(infix_n)
        def non_assoc_logic(x):
            return op_n.bind(lambda f: 
                   result_parser.bind(lambda y: 
                   pure(f(x, y)))) | pure(x)
                   
        result_parser = result_parser.bind(non_assoc_logic)

    return result_parser
