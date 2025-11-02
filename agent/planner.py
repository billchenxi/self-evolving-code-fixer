# agent/planner.py
"""
Planner for the Self-Evolving Code-Fixer.

Public API:
  - summarize_files(workspace: Path, paths: list[str], max_lines: int = 60) -> dict[str, str]
  - plan_fix(memory: dict, test_log: str, file_summaries: dict[str,str], workspace: Path) -> list[dict]

Behavior (MVP):
  - Heuristic fast-path: detect simple off-by-one bug in app/main.py and fix it.
  - Style-aware nudge (very conservative): align quotes if memory["style"] prefers single quotes.
  - Hooks left for skills & web hints (no external deps required).

Patch schema:
  [{"path": "app/main.py", "new_text": "<entire file content>"}]
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Any
import re
import os

# ------------------------------- Utilities ------------------------------------


def summarize_files(
	workspace: Path, paths: List[str], max_lines: int = 60
) -> Dict[str, str]:
    """
	Read a small head of each file for lightweight context (prompting or rules).
	"""
    out: Dict[str, str] = {}
    for rel in paths:
        fp = workspace / rel
        if fp.exists():
            out[rel] = "\n".join(
				fp.read_text(encoding="utf-8").splitlines()[:max_lines]
			)
    return out


def _apply_style(text: str, style: dict | None) -> str:
    """
	Minimal style nudges based on memory["style"] (if present).
	Intentionally conservative: only adjust trivial string quote cases.
	"""
    if not isinstance(style, dict):
        return text
    if style.get("prefer_single_quotes"):
        # extremely conservative swaps for common patterns
        text = text.replace('")', "')").replace('",', "',")
        text = text.replace('= "', "= '").replace(': "', ": '")
    return text


# (Optional) placeholders for future extensions; kept as no-ops for now.


def _load_skills(workspace: Path, memory: Dict[str, Any]) -> Dict[str, Any]:
    """
	Placeholder for dynamic skill loading from .selfevolve/knowledge/... (ingest step).
	MVP returns empty registry to avoid importing unvetted code during first demo.
	"""
    return {}


def _web_hints(test_log: str) -> str:
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key or not test_log:
        return ""
    try:
        from firecrawl import Firecrawl
    except Exception:
        return ""

    if "TypeError" in test_log and "NoneType" in test_log:
        url = "https://docs.python.org/3/tutorial/datastructures.html"
    else:
        url = "https://docs.python.org/3/tutorial/index.html"

    client = Firecrawl(api_key=api_key)
    out = client.scrape(url, formats=["markdown"])

    # Robustly extract markdown from Document or dict
    md = ""
    if hasattr(out, "markdown"):
        md = out.markdown or ""
    elif isinstance(out, dict):
        md = out.get("markdown") or ""
    md = md[:1500]

    return f"Source: {url}\n\n{md}" if md else ""


# -------------------------------- Planner -------------------------------------


def plan_fix(
    memory: Dict[str, Any],
    test_log: str,
    file_summaries: Dict[str, str],
    workspace: Path,
) -> List[dict]:
    """
    Decide on a minimal patch set to try. Keep changes tiny and targeted.

    Strategy (MVP):
      1) Heuristic fast-path: fix classic off-by-one in app/main.py.
      2) If memory contains 'off_by_one', generalize return x - N -> x + 1.
      3) If tests show NoneType TypeError, fetch Firecrawl docs and rewrite
         misuses of in-place list.sort() to sorted(...).
      4) Otherwise, return no patches (let Reflect learn / next iter try again).
    """
    import re

    patches: List[dict] = []

    target = "app/main.py"
    full_path = workspace / target
    if not full_path.exists():
        return patches

    src = full_path.read_text(encoding="utf-8")

    # --- 1) Exact fast-path: inc() off-by-one (-1 -> +1) ----------------------
    m = re.search(r"(?m)^(?P<indent>\s*)return\s+x\s*-\s*1\s*$", src)
    if m:
        new_src = re.sub(
            r"(?m)^(?P<indent>\s*)return\s+x\s*-\s*1\s*$",
            r"\g<indent>return x + 1",
            src,
            count=1,
        )
        # Keep a final newline to avoid EOF layout issues
        if not new_src.endswith("\n"):
            new_src += "\n"
        new_src = _apply_style(new_src, memory.get("style", {}))
        return [{"path": target, "new_text": new_src}]

    # --- 2) Learned generalization: return x - N -> return x + 1 --------------
    has_off_by_one = any(
        h.get("tag") == "off_by_one" for h in memory.get("heuristics", [])
    )
    if has_off_by_one and re.search(r"(?m)^\s*return\s+x\s*-\s*\d+\s*$", src):
        new_src = re.sub(
            r"(?m)^(?P<indent>\s*)return\s+x\s*-\s*\d+\s*$",
            r"\g<indent>return x + 1",
            src,
            count=1,
        )
        if not new_src.endswith("\n"):
            new_src += "\n"
        new_src = _apply_style(new_src, memory.get("style", {}))
        return [{"path": target, "new_text": new_src}]

    # --- 3) Firecrawl-gated fix: list.sort() returns None ---------------------
    # If tests failed with a NoneType TypeError, we consult docs and patch.
    # --- Firecrawl-guided (or fallback) fix for list.sort() returning None ---
    if "TypeError" in (test_log or "") and "NoneType" in (test_log or ""):
        hints = _web_hints(test_log)  # may be "" if no key; we still try to patch
        if hints:
            print(
                "\n--- Firecrawl hint (for planner) ---\n",
                hints[:600],
                "\n------------------------------------\n",
            )
        else:
            print(
                "[planner] Firecrawl hint unavailable (no key or fetch issue); attempting safe sort()→sorted() patch."
            )

        # DEBUG: show we entered the branch
        print("[planner] Trying to rewrite list.sort() misuse in app/main.py")

        src = full_path.read_text(encoding="utf-8")

        # Case A: s = xs.sort(...)[ + optional trailing comment ]
        # allow spaces and an inline '# ...' comment after the ')'
        ASSIGN_SORT = re.compile(
            r"""(?mx)               # multiline, verbose
            ^(?P<lhs>\s*\w+\s*)     # left-hand side, e.g. 's   '
            =\s*
            (?P<arr>\w+)\.sort      # array variable, e.g. 'xs.sort'
            \(
                (?P<args>[^)]*)     # any args: key=..., reverse=...
            \)
            \s*(?:\#.*)?$           # optional trailing comment
            """
        )

        def _fix_assign_sort(m: re.Match) -> str:
            lhs = m.group("lhs")
            arr = m.group("arr")
            args = (m.group("args") or "").strip()
            args = ("," + args) if args else ""
            return f"{lhs}= sorted({arr}{args})"

        new_src = ASSIGN_SORT.sub(_fix_assign_sort, src, count=1)

        # Case B: return xs.sort()[...] → return sorted(xs)[...]
        if new_src == src:
            new_src = re.sub(
                r"""(?mx)
                ^\s*return\s+(\w+)\.sort\(\)\s*(.*)$
                """,
                r"return sorted(\1)\2",
                src,
                count=1,
            )

        if new_src != src:
            print("[planner] Patched list.sort() → sorted(...).")
            new_src = _apply_style(new_src, memory.get("style", {}))
            return [{"path": target, "new_text": new_src}]
        else:
            print("[planner] No list.sort() misuse matched; leaving code unchanged.")

    # --- 4) No confident fix ---------------------------------------------------
    return patches
