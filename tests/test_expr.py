import pytest
from pyparsec.Parsec import Parsec
from pyparsec.Prim import run_parser, pure
from pyparsec.Char import digit, char
from pyparsec.Combinators import many1
from pyparsec.Expr import build_expression_parser, Operator, Infix, Prefix, Postfix, Assoc

def test_arithmetic_precedence():
    # 1. Define atomic terms
    integer = many1(digit()).map(lambda d: int("".join(d)))
    
    # 2. Define Operations
    def add(x, y): return x + y
    def sub(x, y): return x - y
    def mul(x, y): return x * y
    def div(x, y): return x // y
    def neg(x): return -x
    
    # 3. Build Table
    # Level 1: Prefix '-' (Negation)
    # Level 2: *, / (Left Assoc) - Higher precedence
    # Level 3: +, - (Left Assoc) - Lower precedence
    table = [
        [Prefix(char('-').map(lambda _: neg))],
        [Infix(char('*').map(lambda _: mul), Assoc.LEFT),
         Infix(char('/').map(lambda _: div), Assoc.LEFT)],
        [Infix(char('+').map(lambda _: add), Assoc.LEFT),
         Infix(char('-').map(lambda _: sub), Assoc.LEFT)]
    ]
    
    expr_parser = build_expression_parser(table, integer)
    
    def run(s):
        res, _ = run_parser(expr_parser, s)
        return res

    # Basic
    assert run("1+2") == 3
    assert run("2*3") == 6
    
    # Precedence: 2 + 3 * 4 -> 2 + 12 -> 14 (Not 20)
    assert run("2+3*4") == 14
    assert run("2*3+4") == 10
    
    # Associativity: 10 - 5 - 2 -> (10-5)-2 -> 3 (Not 7)
    assert run("10-5-2") == 3
    
    # Prefix: -3 * 2 -> -6
    assert run("-3*2") == -6
    
    # Prefix + Precedence: -2+3 -> 1
    assert run("-2+3") == 1

def test_right_associativity():
    # Power operator ^ is right associative
    # 2 ^ 3 ^ 2 -> 2 ^ 9 -> 512
    integer = many1(digit()).map(lambda d: int("".join(d)))
    
    def power(x, y): return x ** y
    
    table = [
        [Infix(char('^').map(lambda _: power), Assoc.RIGHT)]
    ]
    
    expr = build_expression_parser(table, integer)
    
    assert run_parser(expr, "2^3^2")[0] == 512
