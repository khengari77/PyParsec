from pyparsec.Parsec import Parsec, State, Result, ParseError
from pyparsec.Combinators import many1, choice, option_maybe
from pyparsec.Char import digit, char, spaces, any_char
from pyparsec.Prim import pure, run_parser, try_parse

try:
    from pipe import Pipe, where
except ImportError:
    raise ImportError("Install with 'pyparsec[examples]' to use this example.")

class UnOp:
    def __init__(self, op: str):
        self.op = op

    def __call__(self, a):
        match self.op:
            case '+':
                return a
            case '-':
                return -a
            case _:
                raise ValueError(f"Invalid operator: {self.op}")

    def __str__(self):
        match self.op:
            case '+':
                return "Pos"
            case '-':
                return "Neg"
            case _:
                raise ValueError(f"Invalid operator: {self.op}")

    def __repr__(self):
        return str(self)


class BinOp:
    def __init__(self, op: str):
        self.op = op

    def __call__(self, a, b):
        match self.op:
            case '+':
                return a + b
            case '-':
                return a - b
            case '*':
                return a * b
            case '/':
                if b == 0:
                    raise ValueError("Division by zero")
                return a // b
            case _:
                raise ValueError(f"Invalid operator: {self.op}")

    def __str__(self):
        match self.op:
            case '+':
                return "Add"
            case '-':
                return "Sub"
            case '*':
                return "Mul"
            case '/':
                return "Div"
            case _:
                raise ValueError(f"Invalid operator: {self.op}")

    def __repr__(self):
        return str(self)


class SubExpr:
    def __init__(self, expr):
        self.expr = expr

    def __str__(self):
        return f"SubExpr({self.expr})"

    def __repr__(self):
        return str(self)

    def __call__(self):
        return self.expr


binop: Parsec[BinOp] = lambda op: char(op) >> (lambda _: pure(BinOp(op)))
unop: Parsec[UnOp] = lambda op: char(op) >> (lambda _: pure(UnOp(op)))

negative = unop('-')
positive = unop('+')
add = binop('+')
subtract = binop('-')
multiply = binop('*')
divide = binop('/')


def subexpr() -> Parsec[SubExpr]:
    def parse_subexpr(state: State) -> Result[SubExpr]:
        val, new_state, err = char('(')(state)
        if err or val is None:
            return None, state, err or ParseError(state.pos, "subexpr failed")
        openSubExpr = 1
        expr = ''
        while openSubExpr > 0:
            if not new_state.input:
                return None, state, ParseError(state.pos, "EOF")

            val, new_state, err = (char('(') | char(')') | any_char())(new_state)
            match val:
                case '(':
                    openSubExpr += 1
                case ')':
                    openSubExpr -= 1
                case _:
                    expr += val
        return SubExpr(expr), new_state, None
    return option_maybe(negative | positive) & Parsec(parse_subexpr)


integer = (option_maybe(negative | positive)
            & many1(digit()) >> (lambda x: pure(int(''.join(x)))))

expression = (try_parse(integer)
              | try_parse(subexpr())
              | try_parse(choice([add, subtract, multiply, divide]))
              ) < spaces()

def flatten(l):
    for i in l:
        if isinstance(i, (list, tuple)):
            yield from flatten(i)
        else:
            yield i
@Pipe
def resolveSubExpr(tokens):
    for i, token in enumerate(tokens):
       if isinstance(token, SubExpr):
           subExprTokens = token.expr | evaluate
           tokens[i] = subExprTokens
    return list(flatten(tokens))


@Pipe
def resolveUnop(tokens):
    for i, token in enumerate(tokens):
        if isinstance(token, UnOp) and isinstance(tokens[i+1], int):
            tokens[i+1] = token(tokens[i+1])
            tokens = tokens[:i] + tokens[i+1:]
    return tokens


@Pipe
def resolveBinOp(tokens, ops):
    for i, token in enumerate(tokens):
        if (isinstance(token, BinOp)
        and token.op in ops
        and isinstance(tokens[i-1], int)
        and isinstance(tokens[i+1], int)):
            tokens[i+1] = token(tokens[i-1], tokens[i+1])
            tokens = tokens[:i-1] + tokens[i+1:]
    return tokens


head = Pipe(lambda x: x[0])
evaluate = (head | Pipe(lambda x: list(flatten(x))) | where(lambda x: x is not None) | Pipe(list)
            | resolveSubExpr | resolveUnop | resolveBinOp('/*') | resolveBinOp('+-') | head)

resolve = expression >> evaluate

if __name__ == "__main__":
    test_cases = [
        "2 + 3",          # 5
        "2 * 3",          # 6
        "2 + 3 * 4",      # 14
        "4 * (2 + 3)",    # 20
        "(2 + 3) * 4",    # 20
        "-2 + 3",         # 1
        "-(2 + 3)",       # -5
        "10 / 2 + 3",      # 8
        "10 / (2 - 2)"    # Division by Zero
    ]
    for expr in test_cases:
        results = []
        try:
            result = run_parser(resolve, expr)
            print(f"{expr} = {result}")
        except ValueError as e:
            print(f"{expr}: {e}")

