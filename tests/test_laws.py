# tests/test_laws.py
from hypothesis import given, strategies as st
from pyparsec.Parsec import Parsec, State, SourcePos
from pyparsec.Prim import pure, fail

# Strategy to generate arbitrary values
vals = st.integers() | st.text()

def run_p(p, input_str=""):
    """Helper to run a parser on empty state"""
    state = State(input_str, SourcePos(1, 1), None)
    return p(state)

# 1. Left Identity: return a >>= f  === f a
@given(vals)
def test_monad_left_identity(v):
    f = lambda x: pure(x) # Simple f
    
    lhs = pure(v).bind(f)
    rhs = f(v)
    
    # We compare the RESULTS of running the parsers
    res_lhs = run_p(lhs)
    res_rhs = run_p(rhs)
    
    assert res_lhs.value == res_rhs.value
    assert res_lhs.consumed == res_rhs.consumed

# 2. Right Identity: m >>= return === m
@given(vals)
def test_monad_right_identity(v):
    m = pure(v)
    
    lhs = m.bind(pure)
    rhs = m
    
    res_lhs = run_p(lhs)
    res_rhs = run_p(rhs)
    
    assert res_lhs.value == res_rhs.value

# 3. Associativity: (m >>= f) >>= g === m >>= (\x -> f x >>= g)
@given(st.integers())
def test_monad_associativity(v):
    m = pure(v)
    f = lambda x: pure(x + 1)
    g = lambda y: pure(y * 2)
    
    lhs = m.bind(f).bind(g)
    rhs = m.bind(lambda x: f(x).bind(g))
    
    res_lhs = run_p(lhs)
    res_rhs = run_p(rhs)
    
    assert res_lhs.value == res_rhs.value
