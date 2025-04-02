# PyParsec: A Python Parser Combinator Library

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

PyParsec is a Python library implementing parser combinators, inspired by Haskell's Parsec library. It aims to provide a flexible and composable way to build parsers for various input formats.  This library is currently under active development, with more features, tests, and examples planned.

## Features

*   **Composable Parsers:** Combine simple parsers into more complex ones.
*   **Error Reporting:**  Provides informative error messages with source position.
*   **Monadic Operations:** Uses bind (`>>=`) and alternative (`<|>`) for expressive parser construction.
*   **Support for String Input:** Designed to parse string-based input.
*   **Primitive Parsers:** Basic parsers for characters, strings, and tokens.
*   **Combinators:** A rich set of combinators for sequencing, choice, repetition, and more.

## Installation

You can install PyParsec using pip:

```bash
pip install pyparsec
```

## Project Structure

```
├── LICENSE            # MIT License
├── PyParsec
│   ├── Char.py        # Character-related parsers (e.g., `char`, `digit`, `spaces`)
│   ├── Combinators.py # Parser combinators (e.g., `choice`, `many`, `sepBy`)
│   ├── Parsec.py      # Core `Parsec` class and related structures (State, ParseError, SourcePos)
│   ├── Prim.py        # Primitive parsers (e.g., `pure`, `fail`, `token`, `run_parser`)
│   └── __init__.py    # Makes PyParsec a package
├── conftest.py        # pytest configuration
└── pyproject.toml     # Poetry project configuration
```

## Usage

Here's a simple example to parse a digit:

```python
from PyParsec import Char
from PyParsec import Prim

# Create a parser that parses a digit
digit_parser = Char.digit()

# Test the parser
result, err = Prim.run_parser(digit_parser, "123")

if err:
    print(err)
else:
    print(f"Parsed digit: {result}")
```

## Currently Implemented Modules and Parsers:

*   **`Parsec.py`:**
    *   `SourcePos`:  Represents source position (line, column).
    *   `State`: Represents the parser state (input, position, user state).
    *   `ParseError`:  Represents a parsing error.
    *   `Parsec`:  The core parser class.  Includes `bind`, `__or__`, `label`, and other core methods.
*   **`Prim.py`:**
    *   `pure`:  Creates a parser that always succeeds with a given value.
    *   `fail`:  Creates a parser that always fails.
    *   `try_parse`:  Attempts a parse and resets the state on failure.
    *   `look_ahead`:  Peeks at the input without consuming.
    *   `token`:  Parses a single token.
    *   `many`:  Parses zero or more occurrences of a parser.
    *   `tokens`, `tokens_prime`: parses a specific sequence of chars.
    *   `run_parser`: Executes the parser and returns the result.
    *   `parse_test`:  Tests a parser and prints results/errors.
*   **`Char.py`:**
    *   `char`:  Parses a specific character.
    *   `satisfy`:  Parses a character that satisfies a given predicate.
    *   `one_of`, `none_of`:  Parses characters belonging/not belonging to a list.
    *   `spaces`, `space`, `newline`, `crlf`, `end_of_line`, `tab`, `upper`, `lower`, `alpha_num`, `letter`, `digit`, `hex_digit`, `oct_digit`, `any_char`: Various character-based parsers.
    *   `string`, `string_prime`: Parses a specific string.
*   **`Combinators.py`:**
    *   `choice`: Chooses between multiple parsers.
    *   `count`:  Parses a specific number of occurrences.
    *   `between`: Parses something between opening and closing parsers.
    *   `option`, `option_maybe`, `optional`:  Handles optional parsing with default values or `None`.
    *   `skipMany1`, `many1`: Parses one or more occurrences.
    *   `sep_by`, `sep_by1`, `end_by`, `end_by1`, `sep_end_by`, `sep_end_by1`:  Parses sequences separated and/or terminated by separators.
    *   `chainl`, `chainl1`, `chainr`, `chainr1`:  Operator chaining with left/right associativity.
    *   `eof`:  Matches the end of the input.
    *   `any_token`: Accepts any single token.
    *   `not_followed_by`:  Checks for a negative condition.
    *   `many_till`: Parses until a terminator.
    *   `look_ahead`:  Peek at the next part of the input without consuming it.
    *   `parser_trace`, `parser_traced`: for Debugging

## Missing Features and Future Work

*   **Complete Implementation of Parsec Combinators:**  There are still several combinators from Haskell's Parsec that need to be implemented (e.g.,  `try`, more sophisticated error handling).
*   **More Comprehensive Testing:**  Increased test coverage using `pytest` and `hypothesis`.
*   **Better Error Reporting:** Improved error messages, including source position and expected tokens.
*   **More Examples:** Clear and illustrative examples demonstrating various parsing scenarios (e.g., simple arithmetic expressions, JSON).
*   **Numeric parsing (integers, floats)**
*   **Support for different input types**
*   **Performance Optimization:** Explore optimization opportunities for improved parsing speed.

## Contributing

Contributions are welcome!  If you'd like to contribute to PyParsec, please:

1.  Fork the repository.
2.  Create a feature branch.
3.  Make your changes and add tests.
4.  Submit a pull request.

## License

This project is licensed under the [MIT License](LICENSE).

