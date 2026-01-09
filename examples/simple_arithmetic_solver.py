from pyparsec.Token import TokenParser, LanguageDef
from pyparsec.Expr import build_expression_parser, Operator, Infix, Prefix, Assoc
from pyparsec.Prim import run_parser, lazy
from pyparsec.Char import one_of

# 1. Lexer Configuration
# We define a simple language style for arithmetic
lang = LanguageDef(
    op_start=one_of("+-*/"),
    op_letter=one_of("+-*/"),
    reserved_op_names=["+", "-", "*", "/"]
)
lexer = TokenParser(lang)

# 2. Basic Token Parsers
integer = lexer.integer
parens = lexer.parens
reserved_op = lexer.reserved_op

# 3. Helper Functions for AST/Calculation
def add(x, y): return x + y
def sub(x, y): return x - y
def mul(x, y): return x * y
def div(x, y): 
    if y == 0: raise ValueError("Division by zero")
    return x / y  # float division
def neg(x): return -x

# 4. Operator Table (Precedence and Associativity)
# Ordered from Highest Precedence to Lowest
table = [
    [Prefix(reserved_op("-").map(lambda _: neg))],
    [Infix(reserved_op("*").map(lambda _: mul), Assoc.LEFT),
     Infix(reserved_op("/").map(lambda _: div), Assoc.LEFT)],
    [Infix(reserved_op("+").map(lambda _: add), Assoc.LEFT),
     Infix(reserved_op("-").map(lambda _: sub), Assoc.LEFT)]
]

# 5. The Expression Parser
def expression():
    # A term is either an integer OR an expression inside parentheses.
    # We use 'lazy' because 'expr' is defined in terms of 'term', and 'term' 
    # uses 'expr' (recursion).
    term = parens(lazy(expression)) | integer
    
    # build_expression_parser handles the precedence logic automatically
    return build_expression_parser(table, term)

# The final parser (handles leading whitespace automatically via token parsers)
parser = expression()

if __name__ == "__main__":
    test_cases = [
        "2 + 3",            # 5.0
        "2 * 3",            # 6.0
        "2 + 3 * 4",        # 14.0 (Precedence check)
        "(2 + 3) * 4",      # 20.0 (Parens check)
        "-2 + 3",           # 1.0 (Prefix check)
        "10 / 2 + 3",       # 8.0
        "10 / (2 - 2)"      # Error check
    ]

    print(f"{'Expression':<20} | {'Result':<10}")
    print("-" * 35)

    for expr_str in test_cases:
        try:
            # run_parser returns (Result, Error)
            # We assume success if Error is None
            result, err = run_parser(parser, expr_str)
            
            if err:
                print(f"{expr_str:<20} | Error: {err}")
            else:
                print(f"{expr_str:<20} | {result}")
                
        except ValueError as e:
            print(f"{expr_str:<20} | Runtime Error: {e}")
