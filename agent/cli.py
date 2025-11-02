# agent/cli.py
"""
Command-line entrypoint for the Self-Evolving Code-Fixer.

Usage:
  python -m agent.cli --workspace . [--max-iters 3]

This wires node implementations into the LangGraph topology and runs
the propose → apply → test → reflect loop.
"""

from __future__ import annotations
import argparse
import sys
import json
from pathlib import Path

from agent.graph import compile_app, S
from agent.patcher import write_edits_json, apply_edits
from agent.reflect import load_memory, save_memory, reflect_update
from agent.planner import summarize_files, plan_fix

try:
	import weave  # type: ignore
	weave.init("self-evolving-code-fixer")  # shows up in your W&B account
	_WEAVE = True
except Exception:
	_WEAVE = False

# ------------------------- Node Implementations -------------------------------

def read_context(state: S) -> S:
	"""
	Load memory, summarize a few key files for planning context.
	"""
	ws = Path(state["repo"])
	mem_path = ws / "agent" / "memory.json"
	memory = load_memory(mem_path)
	state["memory"] = memory

	# Summarize a small set of files (expand as needed)
	state["file_summaries"] = summarize_files(
		ws, ["app/main.py", "tests/test_main.py"], max_lines=80
	)
	return state


def node_plan_fix(state: S) -> S:
	"""
	Produce patch proposals. For MVP this is heuristic; later you can
	swap `plan_fix` to call an LLM and keep the same output schema.
	"""
	ws = Path(state["repo"])
	patches = plan_fix(
		state.get("memory", {}),
		state.get("test_log", ""),
		state.get("file_summaries", {}),
		ws,
	)
	state["patches"] = patches
	return state


def node_apply_patch(state: S) -> S:
    """
	Write `.selfevolve/edits.json` for transparency, then apply edits.
	"""
    ws = Path(state["repo"])
    patches = state.get("patches", []) or []
    try:
        if patches:
            write_edits_json(ws, patches)  # visible artifact for VS Code
            apply_edits(ws, patches)  # actually modify the files
        state["error_flag"] = False
    except Exception as e:
        # Hard-stop on unexpected write errors
        state["error_flag"] = True
        state["message"] = f"apply_patch error: {e}"
    return state


def node_run_tests(state: S) -> S:
    """
    Execute pytest with the same interpreter running this agent.
    Captures stdout/stderr and sets pass/fail.
    """
    from pathlib import Path
    import subprocess, sys, os

    ws = Path(state["repo"])
    pytest_args = os.getenv("PYTEST_ARGS", "-q").split()

    cmd = [sys.executable, "-m", "pytest", *pytest_args]
    p = subprocess.run(cmd, cwd=ws, text=True, capture_output=True)

    log = (p.stdout or "") + "\n" + (p.stderr or "")
    state["tests_passed"] = p.returncode == 0
    state["test_log"] = log
    return state


def node_reflect(state: S) -> S:
	"""
	Mine test log for patterns and update memory; bump iteration counter.
	"""
	ws = Path(state["repo"])
	mem = reflect_update(state.get("memory", {}), state.get("test_log", ""))
	save_memory(ws / "agent" / "memory.json", mem)
	state["memory"] = mem
	state["iter"] = state.get("iter", 0) + 1
	return state

# ------------------------------ CLI Main --------------------------------------


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--workspace", default=".", help="Path to repo root")
	ap.add_argument("--max-iters", type=int, default=3, help="Max repair attempts")
	args = ap.parse_args()

	if _WEAVE:
		# Show one consolidated run in Weave, if available
		weave.init("self-evolving-code-fixer")  # type: ignore

	initial = S(
		repo=str(Path(args.workspace).resolve()),
		iter=0,
		max_iters=args.max_iters,
	)

	app = compile_app(
		read_context=read_context,
		plan_fix=node_plan_fix,
		apply_patch=node_apply_patch,
		run_tests=node_run_tests,
		reflect=node_reflect,
	)

	result = app.invoke(initial)

	# -------- Pretty terminal summary --------
	print("\n=== SELF-EVOLVE SUMMARY ===")
	print(f"Attempts: {result.get('iter', 0)} / {args.max_iters}")
	print(f"Tests passed: {bool(result.get('tests_passed'))}")
	if msg := result.get("message"):
		print(f"Note: {msg}")

	print("\n=== TEST OUTPUT (tail) ===")
	tail = (result.get("test_log") or "").splitlines()[-60:]
	print("\n".join(tail))

	# Exit code mirrors success/failure
	sys.exit(0 if result.get("tests_passed") else 1)


if __name__ == "__main__":
	main()
