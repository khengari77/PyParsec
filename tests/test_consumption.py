# tests/test_consumption.py
from pyparsec.Char import char
from pyparsec.Parsec import Error, SourcePos, State
from pyparsec.Prim import try_parse


def test_choice_commits_on_consumption():
    """
    (char('a') >> char('b')) | char('a')
    Input: 'ac'

    1. First parser matches 'a' (consumes).
    2. Then fails on 'c' (expected 'b').
    3. Because it consumed, <|> should NOT try the second option.
    """
    parser = (char("a") >> char("b")) | char("a")

    state = State("ac", SourcePos(1, 1), None)
    result = parser(state)

    # Should be an Error, Consumed=True
    assert result.consumed is True
    assert isinstance(result.reply, Error)
    # The error should be about expecting 'b', not about the second branch
    msgs = [m.text for m in result.reply.error.messages]
    assert "'b'" in msgs


def test_try_reverts_consumption():
    """
    try(char('a') >> char('b')) | char('a')
    Input: 'ac'

    1. First parser matches 'a', fails on 'c'.
    2. try catches the Consumed Error, converts to Empty Error.
    3. State is reset to start ("ac").
    4. <|> sees Empty Error, tries second branch.
    5. Second branch matches 'a'.
    6. Result: Success 'a', rest "c".
    """
    parser = try_parse(char("a") >> char("b")) | char("a")

    state = State("ac", SourcePos(1, 1), None)
    result = parser(state)

    assert result.value == "a"
    assert result.state is not None
    assert result.state.input == "c"
    # Note: Depending on implementation, consumed might be True (from the successful 'a')
    # or False (if the try block completely hid it).
    # Standard Parsec: The successful branch consumes, so result.consumed is True.
