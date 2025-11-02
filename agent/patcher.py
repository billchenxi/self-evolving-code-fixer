# agent/patcher.py
"""
Safe patch writer for the Self-Evolving Code-Fixer.

Public API:
  - write_edits_json(workspace: Path, patches: list[dict]) -> None
  - apply_edits(workspace: Path, patches: list[dict], *, max_files=3, max_total_lines=300) -> None

Patch schema (per item):
  {"path": "app/..relative..file.py", "new_text": "<entire file content>"}

Notes:
- We ONLY allow writes inside the 'app/' directory.
- We cap files touched and total lines changed to avoid runaway edits.
"""

from __future__ import annotations
from pathlib import Path, PurePosixPath
from typing import List, Dict, Any, Tuple
import json
import difflib

_WHITELIST_ROOT = "app"  # restrict writes to this subfolder


def write_edits_json(workspace: Path, patches: List[Dict[str, Any]]) -> None:
    """Persist the proposed edits for transparency (VS Code can read this)."""
    out_dir = workspace / ".selfevolve"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = []
    for p in patches or []:
        payload.append(
            {
                "path": str(PurePosixPath(str(p.get("path", "")))),
                "newText": p.get("new_text", ""),
            }
        )
    (out_dir / "edits.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ----------------------------- Safety helpers ---------------------------------


def _is_safe_path(workspace: Path, rel_path: str) -> bool:
    """Allow only paths under app/ and forbid traversal outside workspace."""
    try:
        rel = PurePosixPath(rel_path)
        # must start with 'app'
        if len(rel.parts) == 0 or rel.parts[0] != _WHITELIST_ROOT:
            return False
        abs_path = (workspace / rel_path).resolve()
        return str(abs_path).startswith(str((workspace / _WHITELIST_ROOT).resolve()))
    except Exception:
        return False


def _validate_schema(patch: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(patch, dict):
        return False, "patch must be a dict"
    if "path" not in patch or "new_text" not in patch:
        return False, "patch requires 'path' and 'new_text'"
    if not isinstance(patch["path"], str):
        return False, "'path' must be a string"
    if not isinstance(patch["new_text"], str):
        return False, "'new_text' must be a string"
    return True, ""


def _count_changed_lines(old_text: str, new_text: str) -> int:
    diff = difflib.unified_diff(
        old_text.splitlines(keepends=False),
        new_text.splitlines(keepends=False),
        lineterm="",
    )
    added = 0
    removed = 0
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return added + removed


# ------------------------------- Applier --------------------------------------


def apply_edits(
    workspace: Path,
    patches: List[Dict[str, Any]],
    *,
    max_files: int = 3,
    max_total_lines: int = 300,
) -> None:
    """
    Apply patches to disk with guardrails.
    Raises ValueError on validation errors or limits exceeded.
    """
    patches = patches or []
    if len(patches) == 0:
        return

    if len(patches) > max_files:
        raise ValueError(f"Too many files to modify ({len(patches)} > {max_files}).")

    total_changed = 0
    to_write: List[Tuple[Path, str]] = []

    for p in patches:
        ok, msg = _validate_schema(p)
        if not ok:
            raise ValueError(f"Invalid patch schema: {msg}")

        rel_path = str(PurePosixPath(p["path"]))
        if not _is_safe_path(workspace, rel_path):
            raise ValueError(
                f"Unsafe path (allowed only under '{_WHITELIST_ROOT}/'): {rel_path}"
            )

        file_path = workspace / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        old_text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        # Normalize newlines to '\n' to keep diffs sane across platforms
        new_text = p["new_text"].replace("\r\n", "\n").replace("\r", "\n")

        changed = _count_changed_lines(old_text, new_text)
        total_changed += changed
        if total_changed > max_total_lines:
            raise ValueError(
                f"Change budget exceeded: {total_changed} lines > limit {max_total_lines}"
            )

        to_write.append((file_path, new_text))

    # If all checks passed, write files
    for fpath, content in to_write:
        fpath.write_text(content, encoding="utf-8")
