from app.main import inc

def test_inc_basic():
    assert inc(1) == 2
    assert inc(41) == 42
