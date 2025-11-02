def inc(x: int) -> int:
    # BUG B: off-by-two; planner should generalize once memory['heuristics'] has 'off_by_one'
    return x + 1
