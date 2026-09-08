#!/usr/bin/env python3
"""Fixture tests for loop-guard's contract enforcement.

The refusal cases are the point. A loop that starts without a usable exit
criterion does not terminate -- it gets interrupted, and "I stopped it" is not
the same outcome as "it finished".
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "skills" / "loop-guard" / "scripts" / "contract.py"

REFUSED = 2


def project() -> Path:
    root = Path(tempfile.mkdtemp())
    (root / ".git").mkdir()
    (root / "src").mkdir()
    (root / "src" / "a.ts").write_text("// TODO: fix\n", encoding="utf-8")
    return root


def run(root: Path, *args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(CONTRACT), *args],
        cwd=str(root), capture_output=True, text=True, timeout=120,
    )
    return proc.returncode, proc.stdout + proc.stderr


def init(root: Path, exit_command: str, cap: str = "5", scope: str = "src/a.ts",
         goal: str = "test goal") -> tuple[int, str]:
    return run(root, "init", "--goal", goal, "--exit-command", exit_command,
               "--max-iterations", cap, "--scope", scope)


# A POSIX criterion. Under cmd.exe this returns non-zero forever, so the loop
# could never terminate successfully -- the exact bug this suite guards.
POSIX_CRITERION = 'test -z "$(grep -rl TODO src/ 2>/dev/null)"'


def main() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"  ok    {name}")
        else:
            print(f"  FAIL  {name} {detail}")
            failures.append(name)

    print("loop-guard: refusals")
    print("--------------------")

    root = project()
    code, _ = init(root, "")
    check("refuses an empty exit command", code == REFUSED, f"(exit {code})")

    code, _ = init(project(), "true", cap="999")
    check("refuses a cap above the limit", code == REFUSED, f"(exit {code})")

    code, _ = init(project(), "true", cap="0")
    check("refuses a cap of zero", code == REFUSED, f"(exit {code})")

    code, out = init(project(), "definitely-not-a-real-command-xyz --flag")
    check("refuses an exit command that cannot run",
          code == REFUSED and "could not run" in out, f"(exit {code})")

    print()
    print("loop-guard: lifecycle")
    print("---------------------")

    root = project()
    code, out = init(root, POSIX_CRITERION, cap="3")
    check("arms a valid contract", code == 0 and "ARMED" in out, f"(exit {code})")

    # Regression: the criterion must actually evaluate. This failed silently
    # when commands ran through cmd.exe instead of bash.
    code, out = run(root, "check")
    check("iteration 1 continues while the criterion is unmet",
          "not met" in out and "CONTINUE" in out)

    (root / "src" / "a.ts").write_text("// fixed\n", encoding="utf-8")
    code, out = run(root, "check")
    check("detects the criterion becoming met (POSIX shell regression)",
          "MET" in out and "STOP" in out, out.strip()[:120])

    # Cap enforcement, with a criterion that never succeeds.
    root = project()
    init(root, "false", cap="2")
    run(root, "check")
    code, out = run(root, "check")
    check("stops at the cap", "cap (2) reached" in out and code == 1, f"(exit {code})")
    check("calls hitting the cap a failure, not a completion",
          "is a failure, not a completion" in out)

    # Milestone tiering.
    root = project()
    init(root, "false", cap="6")
    tiers = []
    for _ in range(5):
        _, out = run(root, "check")
        if "TIER: milestone" in out:
            tiers.append("milestone")
        elif "TIER: iteration" in out:
            tiers.append("iteration")
    check("tiers checks, milestone on the 5th",
          tiers == ["iteration"] * 4 + ["milestone"], str(tiers))

    code, _ = run(project(), "check")
    check("refuses to check with no contract", code == REFUSED, f"(exit {code})")

    print()
    if failures:
        print(f"{len(failures)} FAILED: {', '.join(failures)}")
        return 1
    print("all loop-guard fixtures passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
