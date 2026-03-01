# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-01

### Added

- Core parser combinator engine (`Parsec`, `State`, `SourcePos`, `ParseError`)
- Monadic interface with `bind`, `map`, `label`, and operator overloads (`>>`, `|`, `&`, `<`, `>`)
- Primitive parsers: `pure`, `fail`, `token`, `tokens`, `try_parse`, `lazy`
- Repetition: `many`, `many1`, `skip_many`
- Character parsers: `char`, `satisfy`, `string`, `one_of`, `none_of`, `letter`, `digit`, `space`, `spaces`, and more
- Combinators: `choice`, `count`, `between`, `option`, `option_maybe`, `optional`, `sep_by`, `sep_by1`, `end_by`, `end_by1`, `sep_end_by`, `sep_end_by1`, `chainl`, `chainl1`, `chainr`, `chainr1`, `many_till`, `not_followed_by`, `eof`, `skip_many1`, `any_token`
- Expression parser builder (`build_expression_parser`) with `Infix`, `Prefix`, `Postfix` operators
- Lexer generator (`TokenParser`) with identifier, operator, integer, float, char/string literal, and comment support
- Pre-built language definitions: `empty_def`, `haskell_style`, `java_style`, `python_style`
- Full language lexers: `haskell`, `mondrian`, `python`
- Stack-safe iterative implementation (no Python recursion limits)
- Zero-copy index-based parsing for O(1) input advancement
- Zero runtime dependencies
- PEP 561 `py.typed` marker for typed package support
- Comprehensive test suite (61+ tests) with Hypothesis property-based testing
