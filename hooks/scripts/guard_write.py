#!/usr/bin/env python3
"""PreToolUse guard: block writing secrets, and block writing to .env files.

Matches Write|Edit|MultiEdit|NotebookEdit. Reads the hook payload on stdin and
exits 2 to block -- exit 2 is the only code that actually stops a tool call.

Fails OPEN on internal error. A guard that crashes and blocks every edit gets
disabled within the hour, which leaves you with no guard at all.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from secret_scan import is_env_file, load_config, scan  # noqa: E402


def extract(tool_input: dict) -> tuple[str, str]:
    """Return (path, content-to-scan) across the different edit tool shapes."""
    path = (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or tool_input.get("path")
        or ""
    )

    parts: list[str] = []
    for key in ("content", "new_string", "new_source"):
        value = tool_input.get(key)
        if isinstance(value, str):
            parts.append(value)

    # MultiEdit-style batches.
    for key in ("edits", "changes"):
        edits = tool_input.get(key)
        if isinstance(edits, list):
            for edit in edits:
                if isinstance(edit, dict):
                    for sub in ("new_string", "content", "new_source"):
                        value = edit.get(sub)
                        if isinstance(value, str):
                            parts.append(value)

    return path, "\n".join(parts)


def block(reason: str) -> int:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 2


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0  # fail open

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    path, content = extract(tool_input)
    config = load_config()

    if is_env_file(path):
        return block(
            f"Blocked: writing to an environment file ({path}).\n"
            "Secrets belong outside the repository. If this is a template, "
            "name it .env.example instead."
        )

    if not content:
        return 0

    findings = scan(content, path=path, config=config)
    if not findings:
        return 0

    detail = "\n".join(f"  - {f}" for f in findings[:5])
    more = f"\n  ...and {len(findings) - 5} more" if len(findings) > 5 else ""
    return block(
        f"Blocked: possible secret in {path or 'this write'}.\n{detail}{more}\n\n"
        f"If this is intentional test or example data, either place it under an "
        f"allowlisted path (tests/fixtures/, *.example) or add "
        f"'{config['pragma']}' to the line. Do not disable the guard."
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 -- never block on our own bug
        sys.exit(0)
