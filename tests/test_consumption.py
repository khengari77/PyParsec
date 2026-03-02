# tests/test_consumption.py
from hypothesis import given, assume
from hypothesis import strategies as st

from pyparsec.Char import char
from pyparsec.Parsec import Error, SourcePos, State
from pyparsec.Prim import try_parse


@given(
    st.characters(whitelist_categories=("L", "Nd")),
    st.characters(whitelist_categories=("L", "Nd")),
)
def test_prop_choice_commits_on_consumption(a, b):
    """
    (char(a) >> char(b)) | char(a)
    Input: a + c (where c != b)

    After consuming `a`, failure on the second char should commit —
    <|> must NOT try the second branch.
    """
    assume(a != b)
    # Use a third char that differs from b to trigger failure
    c = chr((ord(b) + 1) % 0x10000) if b != "\uffff" else chr(ord(b) - 1)
    assume(c != b)

    parser = (char(a) >> char(b)) | char(a)
    state = State(a + c, SourcePos(1, 1), None)
    result = parser(state)

    assert result.consumed is True
    assert isinstance(result.reply, Error)
    msgs = [m.text for m in result.reply.error.messages]
    assert f"'{b}'" in msgs


@given(
    st.characters(whitelist_categories=("L", "Nd")),
    st.characters(whitelist_categories=("L", "Nd")),
)
def test_prop_try_reverts_consumption(a, b):
    """
    try(char(a) >> char(b)) | char(a)
    Input: a + c (where c != b)

    try should revert consumption on failure, allowing <|> to try
    the second branch which matches `a`.
    """
    assume(a != b)
    c = chr((ord(b) + 1) % 0x10000) if b != "\uffff" else chr(ord(b) - 1)
    assume(c != b)

    parser = try_parse(char(a) >> char(b)) | char(a)
    state = State(a + c, SourcePos(1, 1), None)
    result = parser(state)

    assert result.value == a
    assert result.state is not None
    assert result.state.remaining == c
