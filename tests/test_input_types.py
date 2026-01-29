from dataclasses import dataclass

from hypothesis import given
from hypothesis import strategies as st

from pyparsec.Parsec import SourcePos
from pyparsec.Prim import run_parser, token, tokens


@given(st.text())
def test_string_and_bytes_behavior(txt):
    s_input = txt
    b_input = txt.encode("utf-8")

    p_str = tokens(lambda x: str(x), lambda p, t: p, "A")
    p_bytes = tokens(lambda x: str(x), lambda p, t: p, b"A")

    res_s, _ = run_parser(p_str, "ABC")
    res_b, _ = run_parser(p_bytes, b"ABC")

    if "ABC".startswith("A"):
        assert res_s == "A"
        assert res_b == b"A"
    else:
        assert res_s is None


@dataclass
class Tok:
    kind: str
    val: str


def test_list_of_objects():
    input_stream = [Tok("ID", "x"), Tok("OP", "="), Tok("NUM", "1")]

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
    assert result == ("x", "=", "1")


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


def test_parsing_tokens_into_ast_object():
    """
    Simulates parsing a stream of Token objects into an AST object.
    Input: [Tok(ID, "x"), Tok(EQ, "="), Tok(INT, "100")]
    Output: AssignmentNode(variable_name="x", value=100)
    """

    # A helper to create a parser for a specific token type
    def match_token(token_type: str):
        return token(
            show_tok=lambda t: f"Token<{token_type}>",
            # If type matches, return value. Else fail.
            test_tok=lambda t: t.value if t.type == token_type else None,
            # Crucial: Update source position based on the Token's logical width
            # This proves we aren't bound to 'character counting' logic
            next_pos=lambda pos, t: SourcePos(pos.line, pos.column + len(t.value), pos.name),
        )

    # Define the grammar: ID "=" INT
    identifier = match_token("ID")
    equals = match_token("EQ")
    number = match_token("INT").map(int)  # Parse string val to python int

    # Combine them to build the AST Object
    # Syntax: x = 100
    assignment_parser = identifier.bind(
        lambda name: equals >> number.map(lambda val: AssignmentNode(name, val))
    )

    # --- Run Scenario 1: Success ---
    token_stream = [MyToken("ID", "total_cost"), MyToken("EQ", "="), MyToken("INT", "42")]

    result, err = run_parser(assignment_parser, token_stream)

    assert err is None
    assert isinstance(result, AssignmentNode)
    assert result.variable_name == "total_cost"
    assert result.value == 42

    # --- Run Scenario 2: Failure (Type Mismatch) ---
    bad_stream = [
        MyToken("ID", "total_cost"),
        MyToken("ID", "wrong_token"),  # Expected EQ
        MyToken("INT", "42"),
    ]

    res_bad, err_bad = run_parser(assignment_parser, bad_stream)

    assert res_bad is None
    assert "Token<EQ>" in str(err_bad)  # Error message should use our show_tok logic
