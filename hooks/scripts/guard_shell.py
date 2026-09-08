#!/usr/bin/env python3
"""PreToolUse guard for Bash and PowerShell.

Two jobs, and the second is the one usually missed:

1. Dangerous commands, in BOTH shell vocabularies. This machine runs PowerShell
   as primary with Git Bash secondary, so a Bash-only guard is a hole and
   `rm -rf` is not even the right idiom.

2. Shell-mediated writes. An edit-tool matcher alone is trivially bypassed by
   `echo "sk-live-..." > .env`. Redirects, tee, sed -i, Set-Content and Out-File
   all write files without touching Write or Edit.

Exits 2 to block. Fails OPEN on internal error.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from secret_scan import is_env_file, load_config, scan  # noqa: E402

# (pattern, why) -- matched case-insensitively against the whole command.
DANGEROUS = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*f|\brm\s+-fr\b"),
     "recursive force delete (rm -rf)"),
    (re.compile(r"\bRemove-Item\b[^|;]*-Recurse\b[^|;]*-Force\b", re.I),
     "recursive force delete (Remove-Item -Recurse -Force)"),
    (re.compile(r"\bRemove-Item\b[^|;]*-Force\b[^|;]*-Recurse\b", re.I),
     "recursive force delete (Remove-Item -Force -Recurse)"),
    (re.compile(r"\bgit\s+push\b[^|;]*(--force\b|(?<![\w-])-f(?![\w-]))"),
     "force push"),
    (re.compile(r"\bcurl\b[^|]*\|\s*(sudo\s+)?(ba)?sh\b"),
     "piping a downloaded script straight into a shell (curl | sh)"),
    (re.compile(r"\bwget\b[^|]*\|\s*(sudo\s+)?(ba)?sh\b"),
     "piping a downloaded script straight into a shell (wget | sh)"),
    (re.compile(r"\b(iwr|irm|Invoke-WebRequest|Invoke-RestMethod)\b[^|]*\|\s*(iex|Invoke-Expression)\b", re.I),
     "piping a downloaded script into Invoke-Expression (iwr | iex)"),
    (re.compile(r"\bgit\s+reset\s+--hard\b[^|;]*\borigin/(main|master)\b"),
     "hard reset onto a remote default branch"),
    (re.compile(r"\bchmod\s+(-R\s+)?777\b"), "world-writable permissions (chmod 777)"),
]

# Commands that write file content through a shell.
WRITE_FORMS = [
    # echo "..." > path   /   >> path   (not >& or 2>)
    re.compile(r"(?P<content>.*?)(?<![0-9>&])>>?\s*(?P<path>[^\s;|&<>]+)"),
    re.compile(r"\|\s*tee\s+(-a\s+)?(?P<path>[^\s;|&<>]+)"),
    re.compile(r"\bsed\s+(-[a-zA-Z]*\s+)*-i\b[^;|]*?(?P<path>[^\s;|&<>]+)\s*$"),
    re.compile(r"\b(Set-Content|Out-File|Add-Content)\b[^;|]*?(?:-Path\s+)?(?P<path>[^\s;|&<>]+)", re.I),
]


HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredocs(command: str) -> str:
    """Remove heredoc bodies before scanning for dangerous commands.

    Writing documentation that mentions `rm -rf` is not running `rm -rf`. This
    guard's first real false positive was a heredoc appending a metrics table
    that quoted the very commands the guard blocks -- so a note about a blocked
    command became a blocked command.

    Bodies are still scanned for secrets separately; only the dangerous-command
    match is narrowed, because that one is about what will *execute*.
    """
    lines = command.splitlines()
    out: list[str] = []
    skip_until: str | None = None

    for line in lines:
        if skip_until is not None:
            if line.strip() == skip_until:
                skip_until = None
            continue

        out.append(line)
        match = HEREDOC.search(line)
        if match:
            skip_until = match.group(2)

    return "\n".join(out)


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


def check_dangerous(command: str) -> str | None:
    for pattern, why in DANGEROUS:
        if pattern.search(command):
            return why
    return None


def check_shell_writes(command: str, config: dict) -> str | None:
    for pattern in WRITE_FORMS:
        for match in pattern.finditer(command):
            groups = match.groupdict()
            path = (groups.get("path") or "").strip("\"'")

            if path and is_env_file(path):
                return (
                    f"writing to an environment file through the shell ({path}). "
                    "Secrets belong outside the repository."
                )

            content = groups.get("content") or command
            findings = scan(content, path=path, config=config)
            if findings:
                return (
                    f"possible secret written through the shell"
                    f"{f' to {path}' if path else ''}:\n  - " + findings[0]
                )
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0

    command = tool_input.get("command") or ""
    if not isinstance(command, str) or not command.strip():
        return 0

    # Dangerous-command matching ignores heredoc bodies: text being written to
    # a file is data, not something about to execute.
    why = check_dangerous(strip_heredocs(command))
    if why:
        return block(
            f"Blocked: {why}.\n\n"
            "If you genuinely intend this, run it yourself in the terminal "
            "with '!' so the decision is explicitly yours."
        )

    config = load_config()
    why = check_shell_writes(command, config)
    if why:
        return block(
            f"Blocked: {why}\n\n"
            f"If this is test or example data, use an allowlisted path "
            f"(tests/fixtures/, *.example) or add '{config['pragma']}' to the line."
        )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001
        sys.exit(0)
