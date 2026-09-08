#!/usr/bin/env python3
"""Structural checks on the harness itself.

Catches the failure modes that do not show up as a crash: a SKILL.md whose
frontmatter stopped parsing, a description that silently exceeds the listing
cap, a hook pointing at a script that no longer exists, or non-ASCII output
that renders as replacement characters on a Windows console.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESCRIPTION_CAP = 1536  # description + when_to_use, per Claude Code docs

FRONTMATTER = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)


def check_frontmatter(failures: list[str]) -> None:
    print("skill frontmatter")
    print("-----------------")
    for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
        rel = skill.relative_to(ROOT).as_posix()
        text = skill.read_text(encoding="utf-8")

        match = FRONTMATTER.match(text)
        if not match:
            print(f"  FAIL  {rel}: no frontmatter at line 1")
            failures.append(rel)
            continue

        body = match.group(1)
        problems = []

        # An unquoted colon in a description is invalid YAML and the skill
        # silently fails to load.
        for line in body.splitlines():
            if not line or line[0] in " \t-#":
                continue
            key, sep, value = line.partition(":")
            if not sep:
                continue
            value = value.strip()
            if value and ":" in value and not (
                value.startswith(('"', "'")) and value.endswith(('"', "'"))
            ):
                problems.append(f"unquoted colon in '{key.strip()}'")

        desc = ""
        for line in body.splitlines():
            if line.startswith("description:"):
                desc = line.partition(":")[2].strip().strip("\"'")
        if not desc:
            problems.append("no description (skill will not auto-invoke)")
        elif len(desc) > DESCRIPTION_CAP:
            problems.append(f"description {len(desc)} chars > {DESCRIPTION_CAP} cap")

        if problems:
            print(f"  FAIL  {rel}: {'; '.join(problems)}")
            failures.append(rel)
        else:
            print(f"  ok    {rel} ({len(desc)} char description)")


def check_hook_targets(failures: list[str]) -> None:
    print()
    print("hook script targets")
    print("-------------------")
    hooks_file = ROOT / "hooks" / "hooks.json"
    if not hooks_file.is_file():
        print("  ok    no hooks.json")
        return

    config = json.loads(hooks_file.read_text(encoding="utf-8"))
    for event, entries in config.get("hooks", {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                for arg in hook.get("args", []):
                    if "${CLAUDE_PLUGIN_ROOT}" not in arg:
                        continue
                    target = ROOT / arg.replace("${CLAUDE_PLUGIN_ROOT}/", "")
                    if target.is_file():
                        print(f"  ok    {event}: {target.name}")
                    else:
                        print(f"  FAIL  {event}: missing {arg}")
                        failures.append(arg)


def check_ascii(failures: list[str]) -> None:
    print()
    print("ascii-only script output")
    print("------------------------")
    for script in sorted(ROOT.rglob("*.py")):
        if ".git" in script.parts:
            continue
        rel = script.relative_to(ROOT).as_posix()
        bad = [
            (i, ch)
            for i, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1)
            for ch in line
            if ord(ch) > 127
        ]
        if bad:
            i, ch = bad[0]
            print(f"  FAIL  {rel}:{i} non-ASCII {ch!r} (+{len(bad) - 1} more)")
            failures.append(rel)
    if not failures:
        print("  ok    all scripts ASCII-only")


def check_allowlist(failures: list[str]) -> None:
    print()
    print("allowlist")
    print("---------")
    path = ROOT / "hooks" / "allowlist.json"
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"  FAIL  allowlist.json: {exc}")
        failures.append("allowlist")
        return
    for key in ("paths", "pragma", "known_examples", "entropy_threshold"):
        if key not in config:
            print(f"  FAIL  allowlist.json missing '{key}'")
            failures.append(key)
    print(f"  ok    {len(config.get('paths', []))} path globs, "
          f"threshold {config.get('entropy_threshold')}")


def main() -> int:
    failures: list[str] = []
    check_frontmatter(failures)
    check_hook_targets(failures)
    check_ascii(failures)
    check_allowlist(failures)

    print()
    if failures:
        print(f"{len(failures)} structural problem(s)")
        return 1
    print("structure ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
