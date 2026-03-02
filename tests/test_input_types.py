from dataclasses import dataclass

from hypothesis import given, assume
from hypothesis import strategies as st

from pyparsec.Parsec import SourcePos
from pyparsec.Prim import run_parser, token, tokens


@given(st.text(min_size=1, max_size=10))
def test_prop_string_tokens(prefix):
    """Property: tokens parser matches string prefixes correctly."""
    p = tokens(lambda x: str(x), lambda p, t: p, prefix)
    # Success case
    res, err = run_parser(p, prefix + "suffix")
    assert res == prefix
    assert err is None

    # Failure case with different first char
    diff = chr((ord(prefix[0]) + 1) % 0x10000)
    if diff != prefix[0]:
        res_fail, err_fail = run_parser(p, diff + prefix[1:])
        assert res_fail is None


@given(st.binary(min_size=1, max_size=10))
def test_prop_bytes_tokens(prefix):
    """Property: tokens parser works with bytes input."""
    p = tokens(lambda x: str(x), lambda p, t: p, prefix)
    res, err = run_parser(p, prefix + b"suffix")
    assert res == prefix
    assert err is None


@dataclass
class Tok:
    kind: str
    val: str


@given(
    st.text(min_size=1, max_size=10, alphabet=st.sampled_from("abcdefghij")),
    st.text(min_size=1, max_size=5, alphabet=st.sampled_from("+-*/")),
    st.integers(min_value=0, max_value=999),
)
def test_prop_list_of_objects(name, op, num):
    """Property: token parser handles lists of arbitrary dataclass objects."""
    input_stream = [Tok("ID", name), Tok("OP", op), Tok("NUM", str(num))]

    def match_kind(k):
        return token(
            show_tok=lambda t: t.kind,
            test_tok=lambda t: t.val if t.kind == k else None,
            next_pos=lambda p, t: SourcePos(p.line, p.column + 1, p.name),
        )

    parser = match_kind("ID") >> (
        lambda x: match_kind("OP") >> (lambda y: match_kind("NUM").map(lambda z: (x, y, z)))
    )

    result, err = run_parser(parser, input_stream)
    assert result == (name, op, str(num))
    assert err is None


@dataclass
class MyToken:
    type: str
    value: str

    def __repr__(self):
        return f"Tok({self.type}, {self.value!r})"


@dataclass
class AssignmentNode:
    variable_name: str
    value: int

    def __repr__(self):
        return f"Assignment({self.variable_name} = {self.value})"


@given(
    st.text(min_size=1, max_size=20, alphabet=st.sampled_from("abcdefghij_")),
    st.integers(min_value=-999, max_value=999),
)
def test_prop_tokens_into_ast(var_name, val):
    """Property: token stream parses into correct AST node for any var/value."""

    def match_token(token_type: str):
        return token(
            show_tok=lambda t: f"Token<{token_type}>",
            test_tok=lambda t: t.value if t.type == token_type else None,
            next_pos=lambda pos, t: SourcePos(pos.line, pos.column + len(t.value), pos.name),
        )

    identifier = match_token("ID")
    equals = match_token("EQ")
    number = match_token("INT").map(int)

    assignment_parser = identifier.bind(
        lambda name: equals >> number.map(lambda v: AssignmentNode(name, v))
    )

    token_stream = [MyToken("ID", var_name), MyToken("EQ", "="), MyToken("INT", str(val))]
    result, err = run_parser(assignment_parser, token_stream)

    assert err is None
    assert isinstance(result, AssignmentNode)
    assert result.variable_name == var_name
    assert result.value == val


@given(st.text(min_size=1, max_size=10, alphabet=st.sampled_from("abcdefghij")))
def test_prop_token_type_mismatch(var_name):
    """Property: wrong token type produces error mentioning expected type."""

    def match_token(token_type: str):
        return token(
            show_tok=lambda t: f"Token<{token_type}>",
            test_tok=lambda t: t.value if t.type == token_type else None,
            next_pos=lambda pos, t: SourcePos(pos.line, pos.column + len(t.value), pos.name),
        )

    identifier = match_token("ID")
    equals = match_token("EQ")
    number = match_token("INT").map(int)

    assignment_parser = identifier.bind(
        lambda name: equals >> number.map(lambda v: AssignmentNode(name, v))
    )

    bad_stream = [
        MyToken("ID", var_name),
        MyToken("ID", "wrong"),  # Expected EQ
        MyToken("INT", "42"),
    ]

    res, err = run_parser(assignment_parser, bad_stream)
    assert res is None
    assert "Token<EQ>" in str(err)
