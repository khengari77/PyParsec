# tests/conftest.py
import pytest

from pyparsec.Parsec import Error, Ok, ParseResult, SourcePos, State


def assert_result_eq(res1: ParseResult, res2: ParseResult):
    """
    Deep comparison of two ParseResults.
    """
    assert res1.consumed == res2.consumed, f"Consumed mismatch: {res1.consumed} != {res2.consumed}"

    # Check Reply Type
    if isinstance(res1.reply, Ok):
        assert isinstance(res2.reply, Ok), "Reply mismatch: Ok vs Error"
        assert res1.reply.value == res2.reply.value
        assert res1.reply.state.pos == res2.reply.state.pos
        assert res1.reply.state.input == res2.reply.state.input
        # Compare error messages (ghost errors)
        assert res1.reply.error.messages == res2.reply.error.messages
    else:
        assert isinstance(res2.reply, Error), "Reply mismatch: Error vs Ok"
        assert res1.reply.error.messages == res2.reply.error.messages
        assert res1.reply.error.pos == res2.reply.error.pos


@pytest.fixture
def initial_state():
    def _make(input_data):
        return State(input_data, SourcePos(1, 1, "test"), None)

    return _make
