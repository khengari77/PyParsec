from hypothesis import given
from hypothesis import strategies as st

from pyparsec.Parsec import SourcePos, update_pos_char, update_pos_string


def slow_reference_update(pos, text):
    curr = pos
    for char in text:
        curr = update_pos_char(curr, char)
    return curr


@given(st.text())
def test_fast_pos_update_matches_reference(text):
    start = SourcePos(1, 1, "test")
    expected = slow_reference_update(start, text)
    actual = update_pos_string(start, text)
    assert actual == expected
