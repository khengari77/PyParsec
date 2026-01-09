# PyParsec

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-passing-green)]()

**PyParsec** is an industrial-strength Parser Combinator library for Python. 

It is a faithful port of Haskell's legendary **Parsec** library, adapted for Python's idioms while maintaining mathematical correctness. Unlike many Python parser libraries, PyParsec is **stack-safe**, **type-safe**, and supports **generic inputs** (strings, bytes, or token lists).

## Key Features

*   **🛡️ Robust Error Handling:** Distinguishes between "Empty" and "Consumed" failures, allowing precise control over backtracking using `try_parse`.
*   **🚀 Stack-Safe Combinators:** `many`, `choice`, and expression chains are implemented iteratively. You won't hit `RecursionError` on large inputs.
*   **🧩 Generic Input:** Parse `str`, `bytes`, or `List[T]` (e.g., tokens from a lexer). The `SourcePos` logic is decoupled from the input type.
*   **🔋 Batteries Included:** Includes the full suite of Parsec modules:
    *   **`Token`**: Automatically generate lexers (whitespace, comments, identifiers) from a language definition.
    *   **`Expr`**: Built-in operator precedence parsing (Infix, Prefix, Postfix).
*   **🐍 Pythonic Operators:** 
    *   `>>` is polymorphic: behaves like Bind (`>>=`) when passed a function, and Sequence (`*>`) when passed a parser.
    *   `|` is Choice (`<|>`).

## Installation

This project is managed with `uv` and `hatchling`. You can install it directly from the repository:

```bash
pip install git+https://github.com/khengari77/PyParsec.git
```

For development:
```bash
git clone https://github.com/khengari77/PyParsec.git
cd PyParsec
uv sync
```

## Quick Start

### 1. Basic Parsing
Parsing a sequence of digits into an integer.

```python
from pyparsec import many1, digit, run_parser, pure

# Logic: Parse one or more digits -> join them -> convert to int
integer = many1(digit()) >> (lambda ds: pure(int("".join(ds))))

result, err = run_parser(integer, "12345")
print(result) # 12345
```

### 2. Using the `Token` Module (Easy Lexing)
Don't write manual regexes. Use `TokenParser` to handle whitespace, comments, and data types automatically.

```python
from pyparsec import TokenParser, python_style, run_parser

# Create a lexer based on Python syntax rules (handling # comments, etc.)
lexer = TokenParser(python_style)

# These parsers automatically skip trailing whitespace/comments!
integer = lexer.integer
parens  = lexer.parens
identifier = lexer.identifier

# Parse: ( count )
parser = parens(identifier)

print(run_parser(parser, "(  my_variable  ) # comments are ignored"))
# Output: ('my_variable', None)
```

### 3. Operator Precedence (`Expr` Module)
Parsing mathematical expressions with correct order of operations (PEMDAS) is often difficult. PyParsec makes it declarative.

```python
from pyparsec import build_expression_parser, Operator, Infix, Assoc, run_parser
from pyparsec import TokenParser, empty_def

# Setup a simple lexer
lexer = TokenParser(empty_def)
integer = lexer.integer

# Define functions
def add(x, y): return x + y
def mul(x, y): return x * y

# Define Operator Table
# Higher precedence comes first!
table = [
    [Infix(lexer.reserved_op("*") >> (lambda _: mul), Assoc.LEFT)],
    [Infix(lexer.reserved_op("+") >> (lambda _: add), Assoc.LEFT)]
]

expr = build_expression_parser(table, integer)

print(run_parser(expr, "2 + 3 * 4")) 
# Output: 14 (not 20!)
```

## Advanced: Generic Input (Parsing Tokens)

PyParsec isn't limited to strings. You can parse a list of objects produced by a separate lexing stage.

```python
from dataclasses import dataclass
from pyparsec import token, run_parser, SourcePos

@dataclass
class Tok:
    kind: str
    value: str

# Define a primitive that consumes a Token object
def match_kind(kind):
    return token(
        show_tok=lambda t: f"Token({kind})",
        test_tok=lambda t: t.value if t.kind == kind else None,
        # Update position based on token logic (optional)
        next_pos=lambda pos, t: SourcePos(pos.line, pos.column + 1, pos.name)
    )

stream = [Tok("ID", "x"), Tok("EQ", "="), Tok("NUM", "10")]

# Grammar: ID = NUM
parser = match_kind("ID") >> match_kind("EQ") >> match_kind("NUM")

print(run_parser(parser, stream))
# Output: '10'
```

## Module Overview

*   **`pyparsec.Prim`**: Core primitives (`pure`, `bind`, `fail`, `try_parse`, `many`).
*   **`pyparsec.Char`**: String-specific parsers (`char`, `string`, `alpha_num`, `one_of`).
*   **`pyparsec.Combinators`**: Logic flow (`choice`, `optional`, `sep_by`, `between`).
*   **`pyparsec.Token`**: Automated lexer generation (`TokenParser`, `LanguageDef`).
*   **`pyparsec.Expr`**: Operator precedence builder (`build_expression_parser`).
*   **`pyparsec.Language`**: Pre-defined language styles (`java_style`, `python_style`, `haskell_style`).

## Contributing

1.  Clone the repo.
2.  Install `uv`.
3.  Run tests: `uv run pytest tests/` (We use Hypothesis for property-based testing).

## License

MIT License.
