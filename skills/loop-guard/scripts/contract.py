#!/usr/bin/env python3
"""Bounded autonomy: a loop that cannot run away.

An autonomous loop without a machine-checkable exit does not terminate -- it
gets interrupted. The difference between "it finished" and "I stopped it"
matters, and only a command's exit code can tell you which happened.

Three preconditions, all required, none inferable:

  1. exit-command   a shell command that exits 0 exactly when the goal is met
  2. max-iterations a hard cap
  3. scope          the files this loop is allowed to touch

Checks are tiered, because running a full verify every iteration turns a
20-iteration refactor into quota destruction:

  every iteration : the exit command, plus tree-check against scope
  every Nth       : the full verification chain
  before stopping : full verify (the caller then runs ship-check)

Usage:
    contract.py init --goal G --exit-command C --max-iterations N --scope F...
    contract.py check
    contract.py status
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

CONTRACT = Path("docs") / "context" / "loop-contract.json"
MILESTONE_EVERY = 5
TIMEOUT = 900

# "Command not found" is reported differently by each shell, and subprocess with
# shell=True uses cmd.exe on Windows and /bin/sh elsewhere. Checking only the
# POSIX code silently armed a loop whose criterion could never run.
NOT_FOUND_CODES = {127, 9009}
NOT_FOUND_MARKERS = (
    "is not recognized as an internal or external command",  # cmd.exe
    "command not found",                                     # sh / bash
    "commandnotfoundexception",                              # PowerShell
)


def looks_unrunnable(code: int, output: str) -> bool:
    if code in NOT_FOUND_CODES:
        return True
    low = output.lower()
    return any(marker in low for marker in NOT_FOUND_MARKERS)


def find_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / ".git").exists():
            return d
    return start


BASH = shutil.which("bash")


def run(command: str, cwd: Path) -> tuple[int, str]:
    """Run a command, preferring bash over the platform default shell.

    subprocess(shell=True) uses cmd.exe on Windows. A POSIX exit criterion such
    as `test -z "$(grep -rl TODO src/)"` then runs with no command substitution
    and returns non-zero forever -- so the loop can never terminate
    successfully, which is the exact failure this skill exists to prevent. It is
    worse than a crash because the command *runs*; it is merely wrong.
    """
    args: list[str] | str = [BASH, "-c", command] if BASH else command
    try:
        proc = subprocess.run(
            args, shell=BASH is None, cwd=str(cwd),
            capture_output=True, text=True, timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {TIMEOUT}s"
    except OSError as exc:
        return 127, str(exc)
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def load(root: Path) -> dict | None:
    try:
        return json.loads((root / CONTRACT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save(root: Path, data: dict) -> None:
    path = root / CONTRACT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def cmd_init(args: argparse.Namespace, root: Path) -> int:
    problems = []
    if not args.goal or not args.goal.strip():
        problems.append("--goal is empty")
    if not args.exit_command or not args.exit_command.strip():
        problems.append("--exit-command is empty")
    if args.max_iterations < 1 or args.max_iterations > 50:
        problems.append("--max-iterations must be between 1 and 50")
    if not args.scope:
        problems.append("--scope lists no files")

    if problems:
        print("LOOP-GUARD: REFUSED")
        print()
        for p in problems:
            print(f"  - {p}")
        print()
        print("A loop without all three of an exit command, a cap, and a declared")
        print("scope does not terminate -- it gets interrupted. Supply them.")
        return 2

    # The exit command must actually run. A typo'd criterion never returns 0,
    # so the loop would burn its entire budget and report failure.
    code, output = run(args.exit_command, root)
    if looks_unrunnable(code, output):
        print("LOOP-GUARD: REFUSED")
        print()
        print(f"  - exit command could not run (exit {code})")
        if output:
            print(f"    {output.splitlines()[0][:160]}")
        print()
        print("A criterion that cannot execute never returns 0, so the loop would")
        print("run to the cap and then claim it failed.")
        return 2

    contract = {
        "goal": args.goal.strip(),
        "exit_command": args.exit_command.strip(),
        "max_iterations": args.max_iterations,
        "scope": list(args.scope),
        "iteration": 0,
        "milestone_every": MILESTONE_EVERY,
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "history": [],
    }
    save(root, contract)

    print("LOOP-GUARD: ARMED")
    print()
    print(f"  goal       {contract['goal']}")
    print(f"  exit when  {contract['exit_command']}  (exit code 0)")
    print(f"  cap        {contract['max_iterations']} iterations")
    print(f"  scope      {', '.join(contract['scope'])}")
    print(f"  milestone  full verify every {MILESTONE_EVERY} iterations")
    print()
    if code == 0:
        print("NOTE: the exit command already returns 0. The goal appears to be")
        print("met before starting -- confirm the criterion tests the right thing.")
    return 0


def cmd_check(root: Path) -> int:
    contract = load(root)
    if contract is None:
        print("LOOP-GUARD: NO CONTRACT")
        print("Run 'contract.py init' first.")
        return 2

    contract["iteration"] += 1
    n = contract["iteration"]
    cap = contract["max_iterations"]

    print(f"ITERATION {n}/{cap}")
    print()

    code, output = run(contract["exit_command"], root)
    if code == 0:
        contract["history"].append({"iteration": n, "result": "goal met"})
        save(root, contract)
        print("EXIT CRITERION: MET")
        print()
        print("STOP - goal reached. Run /harness:verify and /harness:ship-check")
        print("before treating this as finished.")
        return 0

    print(f"EXIT CRITERION: not met (exit {code})")
    if output:
        print(f"  {output.splitlines()[-1][:200]}")

    if n >= cap:
        contract["history"].append({"iteration": n, "result": "cap reached"})
        save(root, contract)
        print()
        print(f"STOP - iteration cap ({cap}) reached without meeting the criterion.")
        print()
        print("This is a failure, not a completion. Report what was attempted and")
        print("what remains. Do not raise the cap and continue without a human")
        print("deciding that is the right call.")
        return 1

    tier = "milestone" if n % contract["milestone_every"] == 0 else "iteration"
    print()
    print(f"TIER: {tier}")
    if tier == "milestone":
        print("  run the full verification chain (/harness:verify) this round")
    else:
        print("  targeted checks only -- do not run the full chain")

    scope = " ".join(contract["scope"])
    print()
    print("REQUIRED THIS ITERATION:")
    print(f"  /harness:tree-check {scope}")
    print("  any file outside that scope is a stop condition, not a warning")

    contract["history"].append({"iteration": n, "result": "continue", "tier": tier})
    save(root, contract)

    print()
    print("CONTINUE")
    return 0


def cmd_status(root: Path) -> int:
    contract = load(root)
    if contract is None:
        print("LOOP-GUARD: NO CONTRACT")
        return 2
    print(f"goal       {contract['goal']}")
    print(f"exit when  {contract['exit_command']}")
    print(f"iteration  {contract['iteration']}/{contract['max_iterations']}")
    print(f"scope      {', '.join(contract['scope'])}")
    print(f"started    {contract['started']}")
    if contract["history"]:
        print("history:")
        for h in contract["history"][-5:]:
            tier = f" ({h['tier']})" if "tier" in h else ""
            print(f"  {h['iteration']}: {h['result']}{tier}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--goal", required=True)
    init.add_argument("--exit-command", required=True)
    init.add_argument("--max-iterations", type=int, required=True)
    init.add_argument("--scope", nargs="+", required=True)

    sub.add_parser("check")
    sub.add_parser("status")

    args = parser.parse_args()
    root = find_root(Path.cwd().resolve())

    if args.command == "init":
        return cmd_init(args, root)
    if args.command == "check":
        return cmd_check(root)
    return cmd_status(root)


if __name__ == "__main__":
    sys.exit(main())
