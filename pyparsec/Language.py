"""Pre-built language definitions and lexers for common programming languages.

This module provides ready-to-use :class:`~pyparsec.Token.LanguageDef` instances
and :class:`~pyparsec.Token.TokenParser` lexers for several language families:

**Base definitions (use as starting points for custom languages):**

- ``empty_def`` -- Minimal language definition with no comments or reserved words.
- ``haskell_style`` -- Haskell-style base with ``{- -}`` block and ``--`` line comments.
- ``java_style`` -- Java/C-style base with ``/* */`` block and ``//`` line comments.
- ``python_style`` -- Python-style base with ``#`` line comments and Python reserved words.

**Complete language definitions:**

- ``haskell98_def`` -- Haskell 98 with standard reserved words and operators.
- ``haskell_def`` -- Extended Haskell with FFI keywords and ``#`` in identifiers.
- ``mondrian_def`` -- Mondrian language definition.

**Pre-built lexers (ready to use):**

- ``haskell`` -- :class:`~pyparsec.Token.TokenParser` for Haskell.
- ``mondrian`` -- :class:`~pyparsec.Token.TokenParser` for Mondrian.
- ``python`` -- :class:`~pyparsec.Token.TokenParser` for Python.

Example::

    >>> from pyparsec import run_parser
    >>> from pyparsec.Language import haskell
    >>> run_parser(haskell.identifier, "foo ")[0]
    'foo'
"""
from dataclasses import replace

from .Char import alpha_num, char, letter, one_of
from .Token import LanguageDef, TokenParser

# Common operator characters used across standard definitions.
_std_op_chars = list(":!#$%&*+./<=>?@\\^|-~")

# -----------------------------------------------------------
# Minimal language definition
# -----------------------------------------------------------

# The most minimal token definition. Use this as the basis for custom definitions.
# Has no comments, standard identifier rules (letter or underscore start), and
# no reserved names or operators.
empty_def = LanguageDef(
    comment_start="",
    comment_end="",
    comment_line="",
    nested_comments=True,
    ident_start=letter() | char("_"),
    ident_letter=alpha_num() | one_of(["_", "'"]),
    op_start=one_of(_std_op_chars),
    op_letter=one_of(_std_op_chars),
    reserved_op_names=[],
    reserved_names=[],
    case_sensitive=True,
)

# -----------------------------------------------------------
# Styles: haskell_style, java_style, python_style
# -----------------------------------------------------------

# Minimal token definition for Haskell-style languages. Provides ``{- -}`` block
# comments, ``--`` line comments, letter-start identifiers, and nestable comments.
haskell_style = replace(
    empty_def,
    comment_start="{-",
    comment_end="-}",
    comment_line="--",
    nested_comments=True,
    ident_start=letter(),
    ident_letter=alpha_num() | one_of(["_", "'"]),
    op_start=one_of(_std_op_chars),
    op_letter=one_of(_std_op_chars),
    reserved_op_names=[],
    reserved_names=[],
    case_sensitive=True,
)

# Minimal token definition for Java/C-style languages. Provides ``/* */`` block
# comments and ``//`` line comments. Note: case_sensitive=False matches original
# Parsec behaviour.
java_style = replace(
    empty_def,
    comment_start="/*",
    comment_end="*/",
    comment_line="//",
    nested_comments=True,
    ident_start=letter(),
    ident_letter=alpha_num() | one_of(["_", "'"]),
    reserved_names=[],
    reserved_op_names=[],
    case_sensitive=False,
)

# Minimal token definition for Python-style languages. Provides ``#`` line comments,
# underscore-start identifiers, and standard Python reserved words and operators.
python_style = replace(
    empty_def,
    comment_start="",
    comment_end="",
    comment_line="#",
    nested_comments=False,
    ident_start=letter() | char("_"),
    ident_letter=alpha_num() | char("_"),
    reserved_names=[
        "def",
        "class",
        "if",
        "else",
        "elif",
        "while",
        "for",
        "return",
        "import",
        "from",
        "try",
        "except",
        "raise",
        "pass",
        "with",
        "as",
        "lambda",
        "yield",
        "None",
        "True",
        "False",
        "await",
        "async",
    ],
    reserved_op_names=[
        "+",
        "-",
        "*",
        "/",
        "%",
        "**",
        "//",
        "==",
        "!=",
        "<",
        ">",
        "<=",
        ">=",
        "=",
        "+=",
        "-=",
        "*=",
        "/=",
    ],
    case_sensitive=True,
)

# -----------------------------------------------------------
# Haskell
# -----------------------------------------------------------

# Language definition for Haskell 98. Extends ``haskell_style`` with standard
# reserved words (let, in, case, of, if, then, else, ...) and operators
# (::, .., =, \\, |, <-, ->, @, ~, =>).
haskell98_def = replace(
    haskell_style,
    reserved_op_names=["::", "..", "=", "\\", "|", "<-", "->", "@", "~", "=>"],
    reserved_names=[
        "let",
        "in",
        "case",
        "of",
        "if",
        "then",
        "else",
        "data",
        "type",
        "class",
        "default",
        "deriving",
        "do",
        "import",
        "infix",
        "infixl",
        "infixr",
        "instance",
        "module",
        "newtype",
        "where",
        "primitive",
        # "as","qualified","hiding"
    ],
)

# Language definition for extended Haskell. Adds FFI keywords (foreign, export,
# _ccall_, _casm_, forall) and allows ``#`` in identifiers.
haskell_def = replace(
    haskell98_def,
    ident_letter=haskell98_def.ident_letter | char("#"),
    reserved_names=haskell98_def.reserved_names
    + ["foreign", "import", "export", "primitive", "_ccall_", "_casm_", "forall"],
)

# Pre-built TokenParser lexer for the Haskell language.
haskell = TokenParser(haskell_def)

# -----------------------------------------------------------
# Mondrian
# -----------------------------------------------------------

# Language definition for the Mondrian language. Uses Java-style comments with
# Mondrian-specific reserved words (case, class, default, extends, ...).
mondrian_def = replace(
    java_style,
    reserved_names=[
        "case",
        "class",
        "default",
        "extends",
        "import",
        "in",
        "let",
        "new",
        "of",
        "package",
    ],
    case_sensitive=True,
)

# Pre-built TokenParser lexer for the Mondrian language.
mondrian = TokenParser(mondrian_def)

# -----------------------------------------------------------
# Python
# -----------------------------------------------------------

# Pre-built TokenParser lexer for the Python language.
python = TokenParser(python_style)
