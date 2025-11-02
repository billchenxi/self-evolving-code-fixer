# tools/democtl.py
from __future__ import annotations
from pathlib import Path
import argparse, textwrap, json, shutil

# --- Bug A/B (inc) --------------------------------------------------------
BUG_A = """\
def inc(x: int) -> int:
    # BUG A: classic off-by-one (-1 instead of +1)
    return x - 1
"""

BUG_B = """\
def inc(x: int) -> int:
    # BUG B: off-by-two; planner should generalize once memory['heuristics'] has 'off_by_one'
    return x - 2
"""

TESTS_AB = """\
from app.main import inc

def test_inc_basic():
    assert inc(1) == 2
    assert inc(41) == 42
"""

FIXED_INC = """\
def inc(x: int) -> int:
    # fixed by Self-Evolve
    return x + 1
"""

# --- Bug C (Firecrawl demo) -----------------------------------------------
BUG_C = """\
def top3(xs):
    # BUG C: list.sort() sorts in place and RETURNS None; using it causes a TypeError
    s = xs.sort()            # s becomes None
    return s[-3:]            # TypeError: 'NoneType' object is not subscriptable
"""

TESTS_C = """\
from app.main import top3

def test_top3_basic():
    assert top3([5,1,9,2,8,3]) == [5,8,9]

def test_top3_dupes():
    assert top3([1,1,2,2,10,4]) == [2,4,10]
"""

# --------------------------------------------------------------------------


def write(p: Path, content: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")


def ensure_memory(root: Path):
    mem = root / "agent" / "memory.json"
    if not mem.exists():
        write(mem, json.dumps({"heuristics": [], "fix_snippets": []}, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument(
        "--scenario", choices=["reset", "bugA", "bugB", "bugC", "fixedA"], required=True
    )
    args = ap.parse_args()

    root = Path(args.root)
    app_main = root / "app" / "main.py"
    tests = root / "tests"

    if args.scenario == "reset":
        se = root / ".selfevolve"
        if se.exists():
            shutil.rmtree(se, ignore_errors=True)
            print("🧹 Cleared .selfevolve/")
        ensure_memory(root)
        print("✅ Reset complete (kept agent/memory.json).")
        return

    if args.scenario == "bugA":
        write(app_main, BUG_A)
        write(tests / "test_main.py", TESTS_AB)
        (tests / "test_top3.py").unlink(missing_ok=True)
        ensure_memory(root)
        print("✅ Seeded BUG A (-1).")
        return

    if args.scenario == "bugB":
        write(app_main, BUG_B)
        write(tests / "test_main.py", TESTS_AB)
        (tests / "test_top3.py").unlink(missing_ok=True)
        ensure_memory(root)
        print("✅ Seeded BUG B (-2).")
        return

    if args.scenario == "bugC":
        write(app_main, BUG_C)
        write(tests / "test_top3.py", TESTS_C)
        (tests / "test_main.py").unlink(missing_ok=True)
        ensure_memory(root)
        print("✅ Seeded BUG C (list.sort() returns None).")
        return

    if args.scenario == "fixedA":
        write(app_main, FIXED_INC)
        write(tests / "test_main.py", TESTS_AB)
        (tests / "test_top3.py").unlink(missing_ok=True)
        ensure_memory(root)
        print("✅ Wrote fixed inc(x).")
        return


if __name__ == "__main__":
    main()
