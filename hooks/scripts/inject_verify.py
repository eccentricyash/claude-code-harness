#!/usr/bin/env python3
"""Stop hook: put the last verification result next to the claim about it.

`verify` produces a deterministic PASS/FAIL block, but the sentence describing
it is still model-generated. Nothing structurally prevents a FAIL being narrated
as success. This does not fix that -- it is mitigation, not enforcement -- but
it keeps the raw block adjacent to any claim, where a reader will see both.

Stop fires on EVERY turn, so three rules keep it from becoming noise:

1. Tail-truncate. A failing suite must not dump thousands of lines into
   additionalContext; that defeats a context-budget-conscious harness.
2. Never inject the same result twice. Otherwise every subsequent turn re-injects
   the same block forever.
3. Never inject a stale PASS. A PASS from three days ago sitting beside an
   unrelated claim manufactures confidence. A FAIL is always worth surfacing.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

MAX_CHARS = 1500
STALE_PASS_SECONDS = 15 * 60  # a PASS older than this is not about this turn


def find_verify_file(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        candidate = d / "docs" / "context" / "last-verify.txt"
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    cwd = Path(payload.get("cwd") or Path.cwd()).resolve()
    verify_file = find_verify_file(cwd)
    if verify_file is None:
        return 0

    try:
        block = verify_file.read_text(encoding="utf-8").strip()
        mtime = verify_file.stat().st_mtime
    except OSError:
        return 0

    if not block:
        return 0

    digest = hashlib.sha256(block.encode("utf-8")).hexdigest()[:16]
    state_file = verify_file.parent / ".last-verify-injected"

    # Rule 2: never inject the same result twice.
    try:
        if state_file.read_text(encoding="utf-8").strip() == digest:
            return 0
    except OSError:
        pass

    failed = "FAIL" in block

    # Rule 3: a stale PASS is worse than silence.
    if not failed and (time.time() - mtime) > STALE_PASS_SECONDS:
        return 0

    # Rule 1: tail-truncate; assertions and stack traces live at the end.
    if len(block) > MAX_CHARS:
        block = "[truncated to last %d chars]\n" % MAX_CHARS + block[-MAX_CHARS:]

    age = int(time.time() - mtime)
    age_text = f"{age}s ago" if age < 120 else f"{age // 60}m ago"

    context = (
        f"Last verification result (from /harness:verify, {age_text}) -- "
        f"this is the raw block from process exit codes:\n\n{block}\n\n"
        "If anything above reads FAIL, do not describe the work as passing, "
        "complete, or working."
    )

    try:
        state_file.write_text(digest, encoding="utf-8")
    except OSError:
        pass

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "Stop",
                    "additionalContext": context,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 -- a reporting hook must never break a turn
        sys.exit(0)
