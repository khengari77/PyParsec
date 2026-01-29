from dataclasses import replace

from .Char import alpha_num, char, letter, one_of
from .Token import LanguageDef, TokenParser

# Common operator characters used in standard definitions
_std_op_chars = list(":!#$%&*+./<=>?@\\^|-~")

# -----------------------------------------------------------
# Minimal language definition
# -----------------------------------------------------------

# This is the most minimal token definition. It is recommended to use
# this definition as the basis for other definitions.
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

# This is a minimal token definition for Haskell style languages.
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

# This is a minimal token definition for Java style languages.
# Note: The original Parsec source defines javaStyle as case_sensitive=False.
# We preserve this behavior for strict compatibility.
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

# This is a minimal token definition for Python style languages.
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

# The language definition for the language Haskell98.
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

# The language definition for the Haskell language.
# Extends Haskell98 with FFI keywords and allows '#' in identifiers.
haskell_def = replace(
    haskell98_def,
    ident_letter=haskell98_def.ident_letter | char("#"),
    reserved_names=haskell98_def.reserved_names
    + ["foreign", "import", "export", "primitive", "_ccall_", "_casm_", "forall"],
)

# A lexer for the Haskell language.
haskell = TokenParser(haskell_def)

# -----------------------------------------------------------
# Mondrian
# -----------------------------------------------------------

# The language definition for the language Mondrian.
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

# A lexer for the Mondrian language.
mondrian = TokenParser(mondrian_def)

# -----------------------------------------------------------
# Python
# -----------------------------------------------------------

# A lexer for the Python language.
python = TokenParser(python_style)
