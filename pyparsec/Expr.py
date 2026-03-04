"""Expression parser builder with support for infix, prefix, and postfix operators.

Use :func:`build_expression_parser` with a table of :class:`Operator` definitions
to construct a parser that respects precedence and associativity.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Generic, TypeVar

from .Combinators import chainl1, chainr1, choice
from .Parsec import Parsec
from .Prim import pure

T = TypeVar("T")


class Assoc(Enum):
    """Operator associativity for use in expression parser tables.

    Members:
        NONE: Non-associative (e.g. comparison operators).
        LEFT: Left-associative (e.g. ``+``, ``-``).
        RIGHT: Right-associative (e.g. ``^``, ``**``).
    """

    NONE = auto()
    LEFT = auto()
    RIGHT = auto()


@dataclass
class Operator(Generic[T]):
    """Base class for expression operators.

    Subclasses :class:`Infix`, :class:`Prefix`, and :class:`Postfix` carry
    the parser and (for infix) the associativity.
    """

    pass


@dataclass
class Infix(Operator[T]):
    """A binary infix operator with a given associativity.

    Attributes:
        parser: A parser that consumes the operator token and returns a
            binary function ``(T, T) -> T``.
        assoc: The :class:`Assoc` associativity of this operator.

    Example::

        >>> from pyparsec.Expr import Infix, Assoc
        >>> from pyparsec.Char import char
        >>> add_op = Infix(char('+').map(lambda _: lambda a, b: a + b), Assoc.LEFT)
    """

    parser: Parsec[Callable[[T, T], T]]
    assoc: Assoc


@dataclass
class Prefix(Operator[T]):
    """A unary prefix operator (e.g. negation).

    Attributes:
        parser: A parser that consumes the operator token and returns a
            unary function ``T -> T``.

    Example::

        >>> from pyparsec.Expr import Prefix
        >>> from pyparsec.Char import char
        >>> neg = Prefix(char('-').map(lambda _: lambda x: -x))
    """

    parser: Parsec[Callable[[T], T]]


@dataclass
class Postfix(Operator[T]):
    """A unary postfix operator (e.g. factorial).

    Attributes:
        parser: A parser that consumes the operator token and returns a
            unary function ``T -> T``.

    Example::

        >>> from pyparsec.Expr import Postfix
        >>> from pyparsec.Char import char
        >>> post_inc = Postfix(char('+').map(lambda _: lambda x: x + 1))
    """

    parser: Parsec[Callable[[T], T]]


def build_expression_parser(table: list[list[Operator[T]]], simple_term: Parsec[T]) -> Parsec[T]:
    """Build a parser for expressions with operators at varying precedence levels.

    Args:
        table: A list of operator groups ordered from lowest to highest precedence.
            Each group is a list of ``Operator`` values (``Infix``, ``Prefix``,
            or ``Postfix``) that share the same precedence level.
        simple_term: A parser for the atomic terms of the expression (e.g. numbers
            or parenthesised sub-expressions).

    Returns:
        A parser that handles the full expression grammar with correct precedence
        and associativity.

    Example::

        >>> from pyparsec import run_parser
        >>> from pyparsec.Char import char, digit
        >>> from pyparsec.Expr import Assoc, Infix, build_expression_parser
        >>> num = digit().map(int)
        >>> table = [[Infix(char('+').map(lambda _: lambda a, b: a + b), Assoc.LEFT)]]
        >>> run_parser(build_expression_parser(table, num), "1+2+3")[0]
        6
    """
    term = simple_term
    for ops in table:
        term = _make_level_parser(ops, term)
    return term


def _make_level_parser(ops: list[Operator[T]], term: Parsec[T]) -> Parsec[T]:
    infix_r: list[Parsec[Callable[[T, T], T]]] = []
    infix_l: list[Parsec[Callable[[T, T], T]]] = []
    infix_n: list[Parsec[Callable[[T, T], T]]] = []
    prefix: list[Parsec[Callable[[T], T]]] = []
    postfix: list[Parsec[Callable[[T], T]]] = []

    for op in ops:
        if isinstance(op, Infix):
            if op.assoc == Assoc.RIGHT:
                infix_r.append(op.parser)
            elif op.assoc == Assoc.LEFT:
                infix_l.append(op.parser)
            else:
                infix_n.append(op.parser)
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
    term_parser = pre_parser.bind(
        lambda f: term.bind(lambda x: post_parser.bind(lambda g: pure(g(f(x)))))
    )

    # 2. Handle Infix
    result_parser = term_parser

    if infix_l:
        op_l: Parsec[Callable[[T, T], T]] = choice(infix_l)
        result_parser = chainl1(result_parser, op_l)

    if infix_r:
        op_r: Parsec[Callable[[T, T], T]] = choice(infix_r)
        result_parser = chainr1(result_parser, op_r)

    if infix_n:
        op_n = choice(infix_n)

        def non_assoc_logic(x: T) -> Parsec[T]:
            return op_n.bind(lambda f: result_parser.bind(lambda y: pure(f(x, y)))) | pure(x)

        result_parser = result_parser.bind(non_assoc_logic)

    return result_parser
