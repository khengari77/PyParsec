# PyParsec: A Python Parser Combinator Library

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

PyParsec is a Python library implementing parser combinators, inspired by Haskell's Parsec library. It provides a functional approach to building complex parsers by combining smaller, simpler parsers. This library aims to be flexible, composable, and easy to use for parsing various text-based formats.

## Key Features

*   **Composable Parsers:** Build complex parsers by combining simpler ones using operators like bind (`>>=` or `>>`) and alternative (`|`).
*   **Monadic Interface:** Leverages functional programming concepts for expressive parser construction.
*   **Informative Error Reporting:** Provides error messages with source position (line, column).
*   **Primitive Parsers:** Includes basic building blocks for parsing characters, strings, and satisfying conditions.
*   **Rich Set of Combinators:** Offers combinators for sequencing, choice, repetition (zero or more, one or more), separation, optional parsing, lookahead, and more.
*   **String Input:** Primarily designed for parsing string inputs.

## Installation

You can install PyParsec directly from git using pip (I hope it'll be soon available on PyPI):

```bash
pip install git+https://github.com/khengari77/PyParsec.git
```

To run the examples provided in the `examples/` directory, you might need additional dependencies. You can install them using:

```bash
pip install "git+https://github.com/khengari77/PyParsec.git#egg=pyparsec[examples]"
```

## Basic Usage: Parsing an Integer

Here's a simple example demonstrating how to parse a sequence of digits into an integer:

```python
from pyparsec.Char import digit
from pyparsec.Combinators import many1
from pyparsec.Prim import run_parser, pure

# Define a parser for one or more digits
# many1(digit()) parses one or more digit characters into a list (e.g., ['1', '2', '3'])
# >> (lambda ds: ...) sequences the parser with a function (think of bind)
# pure(int("".join(ds))) converts the list of digits to a string, then to an int,
#                       and lifts the result back into a successful parser.
integer_parser = many1(digit()) >> (lambda digits: pure(int("".join(digits))))

# Input string to parse
input_string = "12345abc"

# Run the parser
result, error = run_parser(integer_parser, input_string)

# Check the result
if error:
    print(f"Parsing failed: {error}")
else:
    print(f"Parsed integer: {result}")
    # Output: Parsed integer: 12345
```

## More Examples

For more complex parsing scenarios, such as building a solver for simple arithmetic expressions, please refer to the examples provided in the `examples/` directory. The `SimpleArithmeticSolver.py` demonstrates the use of various combinators, operator precedence parsing, and handling nested expressions.

## Overview of Modules and Parsers

The library is organized into several modules:

*   **`pyparsec.Parsec`:**
    *   Defines the core `Parsec` class, `State`, `SourcePos`, and `ParseError`.
    *   Implements fundamental operations like bind (`bind`, `>>`), alternative (`__or__`, `|`), sequencing (`__and__`, `&`, `__lt__`, `<`, `__gt__`, `>`), and labeling (`label`).
*   **`pyparsec.Prim`:**
    *   Provides primitive parser constructors and runners.
    *   `pure`: Creates a parser that always succeeds with a given value without consuming input.
    *   `fail`: Creates a parser that always fails with a message.
    *   `try_parse`: Attempts a parse, backtracking (resetting state) on failure.
    *   `look_ahead`: Peeks at the input without consuming it.
    *   `token`, `tokens`, `tokens_prime`: Low-level token and sequence parsers.
    *   `many`: Parses zero or more occurrences of a parser.
    *   `run_parser`: Executes a parser on an input string.
    *   `parse_test`: Helper to run a parser and print the result or error.
*   **`pyparsec.Char`:**
    *   Contains parsers specifically for characters and strings.
    *   `char`: Parses a specific character.
    *   `satisfy`: Parses a character matching a predicate.
    *   `one_of`, `none_of`: Parses characters from/not from a given set.
    *   `space`, `spaces`, `newline`, `crlf`, `end_of_line`, `tab`: Whitespace and newline parsers.
    *   `upper`, `lower`, `alpha_num`, `letter`, `digit`, `hex_digit`, `oct_digit`: Character category parsers.
    *   `any_char`: Parses any single character.
    *   `string`, `string_prime`: Parses a specific string (consuming or non-consuming).
*   **`pyparsec.Combinators`:**
    *   Offers higher-level combinators to build complex parsers.
    *   `choice`: Tries a list of parsers in order.
    *   `count`: Parses a fixed number of occurrences.
    *   `between`: Parses content enclosed by delimiters.
    *   `option`, `option_maybe`, `optional`: Handles optional parts of the input.
    *   `many1`, `skip_many1`: Parses one or more occurrences.
    *   `sep_by`, `sep_by1`, `end_by`, `end_by1`, `sep_end_by`, `sep_end_by1`: Parses sequences with separators.
    *   `chainl`, `chainl1`, `chainr`, `chainr1`: Handles left/right-associative operators (e.g., for expression parsing).
    *   `eof`: Succeeds only at the end of the input.
    *   `any_token`: Parses any single token (character in this context).
    *   `not_followed_by`: Succeeds if a parser fails (negative lookahead).
    *   `many_till`: Parses occurrences until a terminator parser succeeds.
    *   `look_ahead`: (Re-exported from `Prim`) Peeks at the input.
    *   `parser_trace`, `parser_traced`: Utilities for debugging parsers.

## Roadmap and Future Plans

PyParsec is under active development. Future enhancements may include:

*   **More Combinators:** Implementing additional standard Parsec combinators.
*   **Enhanced Error Reporting:** Providing more detailed and user-friendly error messages (e.g., expected vs. actual).
*   **Broader Input Types:** Exploring support for input types beyond strings (e.g., lists of tokens, byte streams).
*   **Performance Optimization:** Investigating potential performance improvements.
*   **Comprehensive Documentation:** Expanding API documentation and tutorials.
*   **More Examples:** Adding examples for common parsing tasks (e.g., JSON, CSV, simple languages).
*   **Robust Testing:** Increasing test coverage, potentially using property-based testing.

## Contributing

Contributions are welcome! If you'd like to contribute to PyParsec, please follow these steps:

1.  Fork the repository on GitHub.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes and add corresponding tests.
4.  Ensure tests pass.
5.  Submit a pull request with a clear description of your changes.

## License

This project is licensed under the [MIT License](LICENSE).
