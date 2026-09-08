#!/usr/bin/env python3
"""Report every file the working tree has changed, including untracked ones.

`git diff --stat` shows tracked modifications only, so a newly created file is
invisible to it -- and "the agent added a file nobody asked for" is exactly the
failure this gate exists to catch. This uses `git status --porcelain`, where
untracked files appear with a `??` status.

Known limit, stated rather than hidden: --porcelain honours .gitignore, so a
write into an ignored path (node_modules/, .next/, dist/) is not reported.
Pass --ignored to include those; it is noisy, so it is opt-in.

Usage:
    tree_check.py                       list changes
    tree_check.py --expected a.ts b.ts  compare against a declared file list
    tree_check.py --ignored             also report gitignored writes
"""
from __future__ import annotations

import argparse
import subprocess
import sys

STATUS_LABEL = {
    "??": "added (untracked)",
    "!!": "written (gitignored)",
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied",
    "U": "conflicted",
}


def git(args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return proc.returncode, proc.stdout


def parse_porcelain(output: str) -> list[tuple[str, str]]:
    """Return (path, human-readable status) for each changed file."""
    entries: list[tuple[str, str]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip()
        # Renames are reported as "old -> new"; the new path is what changed.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip('"')
        key = code.strip() or code
        label = STATUS_LABEL.get(code) or STATUS_LABEL.get(key[:1], f"changed ({code})")
        entries.append((path, label))
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", nargs="*", default=None)
    parser.add_argument("--ignored", action="store_true")
    args = parser.parse_args()

    code, _ = git(["rev-parse", "--is-inside-work-tree"])
    if code != 0:
        print("TREE-CHECK: NOT A GIT REPO")
        print()
        print("Scope checking needs git. Nothing to compare against.")
        return 2

    status_args = ["status", "--porcelain"]
    if args.ignored:
        status_args.append("--ignored")

    code, output = git(status_args)
    if code != 0:
        print("TREE-CHECK: GIT ERROR")
        print(output)
        return 2

    entries = parse_porcelain(output)
    actual = {path for path, _ in entries}

    if args.expected is None:
        print(f"CHANGED FILES: {len(actual)}")
        print()
        for path, label in sorted(entries):
            print(f"  {label:<20} {path}")
        if not entries:
            print("  (working tree clean)")
        if not args.ignored:
            print()
            print("Note: gitignored paths not shown. Re-run with --ignored to include.")
        return 0

    expected = {p.replace("\\", "/").lstrip("./") for p in args.expected}
    normalised = {p.replace("\\", "/").lstrip("./") for p in actual}

    unexpected = sorted(normalised - expected)
    missing = sorted(expected - normalised)

    print(f"Expected files changed: {len(expected)}")
    print(f"Actual:                 {len(normalised)}")
    print(f"Unexpected:             {len(unexpected)}")
    print(f"Declared but untouched: {len(missing)}")

    if unexpected:
        print()
        print("UNEXPECTED (changed but not in the plan):")
        for path in unexpected:
            label = next((l for p, l in entries if p.replace("\\", "/") == path), "changed")
            print(f"  {label:<20} {path}")

    if missing:
        print()
        print("DECLARED BUT UNTOUCHED:")
        for path in missing:
            print(f"  {path}")

    print()
    print("TREE-CHECK: FAIL" if unexpected else "TREE-CHECK: PASS")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
