#!/usr/bin/env python3
"""Fixture tests for the Stop hook's injection rules.

The hook fires every turn, so the rules that keep it quiet are as important as
the one that makes it speak.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "scripts" / "inject_verify.py"

PASS_BLOCK = "TYPECHECK:  PASS\nLINT:       PASS\nTEST:       PASS\n"
FAIL_BLOCK = "TYPECHECK:  PASS\nTEST:       FAIL (exit 1)\n"


def run(cwd: Path) -> str:
    payload = json.dumps({"cwd": str(cwd), "hook_event_name": "Stop"})
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input=payload,
        capture_output=True, text=True, timeout=30,
    )
    if not proc.stdout.strip():
        return ""
    return json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]


def make_project(block: str, age_seconds: int = 0) -> Path:
    root = Path(tempfile.mkdtemp())
    ctx = root / "docs" / "context"
    ctx.mkdir(parents=True)
    target = ctx / "last-verify.txt"
    target.write_text(block, encoding="utf-8")
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(target, (old, old))
    return root


CASES = [
    ("fresh FAIL is injected", FAIL_BLOCK, 0, True),
    ("fresh PASS is injected", PASS_BLOCK, 0, True),
    ("stale PASS is silent", PASS_BLOCK, 60 * 60, False),
    ("stale FAIL is still injected", FAIL_BLOCK, 60 * 60, True),
]


def main() -> int:
    failures = []
    print("stop hook")
    print("---------")

    for name, block, age, expect in CASES:
        root = make_project(block, age)
        out = run(root)
        got = bool(out)
        if got == expect:
            print(f"  ok    [{'inject' if got else 'silent'}] {name}")
        else:
            print(f"  FAIL  [{'inject' if got else 'silent'}] {name}")
            failures.append(name)

    # Rule 2: the same result is never injected twice.
    root = make_project(FAIL_BLOCK)
    first, second = run(root), run(root)
    if first and not second:
        print("  ok    [silent] same result is not injected twice")
    else:
        print("  FAIL  same result injected twice")
        failures.append("dedup")

    # Rule 1: long output is tail-truncated.
    root = make_project("TEST: FAIL\n" + ("x" * 9000))
    out = run(root)
    if "truncated" in out and len(out) < 3000:
        print("  ok    [inject] long output is tail-truncated")
    else:
        print(f"  FAIL  truncation (len={len(out)})")
        failures.append("truncation")

    # No project, no noise.
    if not run(Path(tempfile.mkdtemp())):
        print("  ok    [silent] no verify file means no output")
    else:
        print("  FAIL  emitted output with no verify file")
        failures.append("no-file")

    print()
    if failures:
        print(f"{len(failures)} FAILED: {', '.join(failures)}")
        return 1
    print("all stop-hook fixtures passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
