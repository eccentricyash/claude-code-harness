#!/usr/bin/env python3
"""Fixture tests for the verify runner's config parsing and gate ordering.

The quote-stripping case here is a regression test for a bug that was invisible
under cmd.exe and only surfaced once commands ran through bash: str.strip('"')
removes quote characters from both ends independently, so `echo "types ok"`
became `echo "types ok` -- an unterminated quote. Every verify command
containing quotes was silently mangled.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "skills" / "verify" / "scripts" / "run_verify.py"


def project(yaml_body: str) -> Path:
    root = Path(tempfile.mkdtemp())
    (root / ".git").mkdir()
    rules = root / ".claude" / "rules"
    rules.mkdir(parents=True)
    (rules / "verify.md").write_text(
        f"# Verification chain\n\n```yaml\n{yaml_body}\n```\n", encoding="utf-8"
    )
    return root


def run(root: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(RUNNER)], cwd=str(root),
        capture_output=True, text=True, timeout=300,
    )
    return proc.returncode, proc.stdout + proc.stderr


def stage(out: str, name: str, verdict: str) -> bool:
    """Whitespace-insensitive check for one stage line."""
    return bool(re.search(rf"^{name}:\s+{verdict}", out, re.M))


def main() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  ok    {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("verify runner")
    print("-------------")

    # Regression: a command containing quotes must survive parsing intact.
    root = project(
        'verification:\n'
        '  typecheck: echo "types ok"\n'
        '  lint: echo \'lint ok\'\n'
        '  test: exit 1\n'
        '  build: echo skipped\n'
    )
    code, out = run(root)
    check("a quoted command is not mangled by quote stripping",
          stage(out, "TYPECHECK", "PASS"), out.splitlines()[0] if out else "")
    check("single-quoted command also survives", stage(out, "LINT", "PASS"))
    check("a failing gate short-circuits later stages",
          stage(out, "TEST", "FAIL") and stage(out, "BUILD", "SKIPPED"))
    check("exit code reflects failure", code == 1, f"(exit {code})")

    # A fully-quoted value should still be unwrapped.
    root = project('verification:\n  test: "exit 0"\n')
    _, out = run(root)
    check("a fully-quoted value is unwrapped and runs", stage(out, "TEST", "PASS"))

    # null must be visible, not silently skipped.
    root = project('verification:\n  typecheck: null\n  test: exit 0\n')
    code, out = run(root)
    check("null is reported as NOT CONFIGURED",
          stage(out, "TYPECHECK", "NOT CONFIGURED"))
    check("a project with only passing stages exits 0", code == 0, f"(exit {code})")

    # `run` is recorded but never executed.
    root = project('verification:\n  test: exit 0\n  run: sleep 600\n')
    code, out = run(root)
    check("the run stage is never executed", stage(out, "RUN", "NOT RUN"))

    # No config at all.
    empty = Path(tempfile.mkdtemp())
    (empty / ".git").mkdir()
    code, out = run(empty)
    check("missing config reports NO CONFIG", "VERIFY: NO CONFIG" in out and code == 2)

    print()
    if failures:
        print(f"{len(failures)} FAILED: {', '.join(failures)}")
        return 1
    print("all verify fixtures passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
