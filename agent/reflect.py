# agent/reflect.py
"""
Reflection/memory utilities for the Self-Evolving Code-Fixer.

Public API:
  - load_memory(mem_path: Path) -> dict
  - save_memory(mem_path: Path, memory: dict) -> None
  - reflect_update(memory: dict, test_log: str) -> dict

Memory schema (JSON):
{
  "heuristics": [
    {"tag":"off_by_one","pattern":"AssertionError.*==","advice":"Check +/- 1 around arithmetic or index bounds."},
    {"tag":"none_guard","pattern":"TypeError:.*NoneType","advice":"Guard None inputs before arithmetic or attribute access."}
  ],
  "fix_snippets": [],           # (optional) small text snippets you decide to keep
  "style": {...},               # (optional) from ingest
  "knowledge_packs": [ ... ]    # (optional) from ingest
}
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
import json, re, time


# ---------------------------- Persistence -------------------------------------


def load_memory(mem_path: Path) -> Dict[str, Any]:
    try:
        if mem_path.exists():
            raw = mem_path.read_text(encoding="utf-8")
            mem = json.loads(raw or "{}")
        else:
            mem = {}
    except Exception:
        mem = {}

    mem.setdefault("heuristics", [])
    mem.setdefault("fix_snippets", [])
    # optional keys "style", "knowledge_packs" may be set by ingest
    return mem


def save_memory(mem_path: Path, memory: Dict[str, Any]) -> None:
    mem_path.parent.mkdir(parents=True, exist_ok=True)
    # keep a tiny timestamp for debugging (not used by logic)
    memory["_updated_at"] = int(time.time())
    mem_path.write_text(json.dumps(memory, indent=2), encoding="utf-8")


# ---------------------------- Heuristic mining --------------------------------

# Minimal patterns that frequently show up in kata/real repos
_PATTERNS = [
    {
        "tag": "off_by_one",
        "regex": r"AssertionError.*==",
        "advice": "Check +/- 1 around arithmetic or index bounds. Verify len/slicing.",
    },
    {
        "tag": "none_guard",
        "regex": r"TypeError: .*NoneType",
        "advice": "Guard None inputs or provide defaults before arithmetic/attribute access.",
    },
    {
        "tag": "index_bounds",
        "regex": r"IndexError: list index out of range",
        "advice": "Verify bounds; prefer enumerate or range(len(...))-1 checks.",
    },
    {
        "tag": "key_missing",
        "regex": r"KeyError: .+",
        "advice": "Use dict.get with default or check key existence before access.",
    },
    {
        "tag": "import_missing",
        "regex": r"(ModuleNotFoundError|ImportError):\s*No module named\s+'?([\w\.]+)'?",
        "advice": "Confirm package/install or relative import path; avoid shadowing stdlib names.",
    },
    {
        "tag": "type_mismatch",
        "regex": r"TypeError: .* (unsupported operand type|expected .* got .*)",
        "advice": "Add type guards/casts; keep operations between compatible types.",
    },
    
]


def _dedupe(
    seq: List[Dict[str, Any]], key=("tag", "regex", "advice"), max_items: int = 64
) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for item in seq:
        k = tuple(item.get(k, "") for k in key)
        if k not in seen:
            seen.add(k)
            out.append(item)
        if len(out) >= max_items:
            break
    return out


def reflect_update(memory: Dict[str, Any], test_log: str) -> Dict[str, Any]:
    """
    Inspect pytest output and add lightweight heuristics.
    Returns the updated memory (does not write to disk).
    """
    if not isinstance(memory, dict):
        memory = {"heuristics": [], "fix_snippets": []}
    memory.setdefault("heuristics", [])
    memory.setdefault("fix_snippets", [])

    log = test_log or ""

    new_rules: List[Dict[str, Any]] = []
    for pat in _PATTERNS:
        if re.search(pat["regex"], log, flags=re.IGNORECASE | re.DOTALL):
            new_rules.append(
                {
                    "tag": pat["tag"],
                    "pattern": pat["regex"],
                    "advice": pat["advice"],
                }
            )

    # Example: capture missing symbol from NameError to guide future prompts
    m = re.search(r"NameError:\s*name\s+'?([\w_]+)'?\s+is not defined", log)
    if m:
        sym = m.group(1)
        new_rules.append(
            {
                "tag": "name_error",
                "pattern": rf"NameError:.*\b{re.escape(sym)}\b",
                "advice": f"Define or import '{sym}' before use; check scope.",
            }
        )

    # Merge, dedupe, and clip
    memory["heuristics"] = _dedupe(list(memory["heuristics"]) + new_rules)

    return memory
