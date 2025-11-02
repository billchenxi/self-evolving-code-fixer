# agent/graph.py
"""
LangGraph wiring for the Self-Evolving Code-Fixer.

This module ONLY defines:
  - the State type (S)
  - the graph topology (build_graph)
  - a convenience runner (compile_app)

Nodes (callables) are injected from your other modules, so you can
evolve implementations (LLM vs. heuristic) without touching topology.
"""
from __future__ import annotations
from typing import Callable, Dict, Any, TypedDict, Optional
from langgraph.graph import StateGraph, END
import os

try:
	import weave  # type: ignore

	_WEAVE_IMPORTED = True
except Exception:
	_WEAVE_IMPORTED = False

# Opt-in via env var: set WEAVE_TRACE=1 to enable tracing.
_WEAVE_AVAILABLE = _WEAVE_IMPORTED and os.getenv("WEAVE_TRACE") == "1"


class S(TypedDict, total=False):
	"""
	Central state passed between nodes.

	Required at entry:
		repo: str               # absolute path to workspace root
		max_iters: int          # max repair attempts
		iter: int               # current attempt index

	Populated/updated by nodes:
		memory: Dict[str, Any]          # reflection memory (heuristics/snippets)
		file_summaries: Dict[str, str]  # small context map for planner
		patches: list[Dict[str, Any]]   # proposed edits [{"path","new_text"}]
		tests_passed: bool              # test result from last RunTests
		test_log: str                   # pytest stdout/stderr
		error_flag: bool                # fatal error → stop
		message: str                    # optional human-friendly status
	"""
	repo: str
	max_iters: int
	iter: int

	memory: Dict[str, Any]
	file_summaries: Dict[str, str]
	patches: list[Dict[str, Any]]
	tests_passed: bool
	test_log: str
	error_flag: bool
	message: str
 
	plans: int
	applies: int
	runs: int
	reflects: int

# Node signature each step must implement.
NodeFn = Callable[[S], S]

def _trace(fn: NodeFn, name: str) -> NodeFn:
	if not _WEAVE_AVAILABLE:
		return fn

	@weave.op(name=f"node::{name}")
	def traced(state: S) -> S:
		return fn(state)

	return traced  # type: ignore[return-value]

def _route_after_apply(state: S) -> str:
	# Stop on fatal error; otherwise go run tests (even if no new patches).
	if state.get("error_flag"):
		return END
	return "RunTests"

def _route_after_tests(state: S):
	if state.get("error_flag"):
		return END
	if state.get("test_passed"):
		return END
	if state.get("iter", 0) + 1 >= state.get("max_iters", 3):
		return END
	return "Reflect"

def build_graph(
	read_context: NodeFn,
 	plan_fix,
	apply_patch,
 	run_tests,
  	reflect
):
	g = StateGraph(S)

	g.add_node("ReadContext", _trace(read_context, "ReadContext"))
	g.add_node("PlanFix", _trace(plan_fix, "PlanFix"))
	g.add_node("ApplyPatch", _trace(apply_patch, "ApplyPatch"))
	g.add_node("RunTests", _trace(run_tests, "RunTests"))
	g.add_node("Reflect", _trace(reflect, "Reflect"))
	
	g.set_entry_point("ReadContext")
	g.add_edge("ReadContext", "PlanFix")
	g.add_edge("PlanFix", "ApplyPatch")
	g.add_conditional_edges("ApplyPatch", _route_after_apply, {"RunTests": "RunTests", END: END})
	g.add_conditional_edges("RunTests", _route_after_tests, {"Reflect": "Reflect", END: END})
	g.add_edge("Reflect", "PlanFix")

	return g.compile()

def compile_app(
	read_context: NodeFn,
	plan_fix: NodeFn,
	apply_patch: NodeFn,
	run_tests: NodeFn,
	reflect: NodeFn,
):
	return build_graph(read_context, plan_fix, apply_patch, run_tests,reflect)
