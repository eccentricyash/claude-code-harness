#!/usr/bin/env python3
"""Run a project's declared verification chain and emit a machine-readable result.

The model never decides PASS/FAIL here. Every verdict comes from a process exit
code. The model's only job is to read this block and attach raw output for
failures.

Config lives in <project>/.claude/rules/verify.md as the first ```yaml fence:

    verification:
      typecheck: npm run typecheck
      lint:      npm run lint
      test:      npm test
      build:     npm run build
      run:       npm run dev

A stage set to `null` is reported NOT CONFIGURED rather than silently skipped --
a missing test suite should be visible, not invisible.

Exit codes: 0 all configured gates passed, 1 a gate failed, 2 no config found.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Ordered: a failure short-circuits everything after it.
STAGES = ["typecheck", "lint", "test", "build"]
# `run` starts a long-lived process; it is never executed here.
RUNTIME_STAGE = "run"

MAX_OUTPUT = 4000  # chars of raw output kept per failing stage


def find_project_root(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        if (d / ".claude" / "rules" / "verify.md").is_file():
            return d
    return None


def parse_config(path: Path) -> dict[str, str | None]:
    """Extract the `verification:` mapping from the first ```yaml fence.

    Deliberately a small hand parser: this must run with a bare interpreter and
    no pip install, on a machine where PyYAML may not be present.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    in_fence = False
    in_verification = False
    config: dict[str, str | None] = {}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            # Only consume the first fence.
            if in_fence:
                break
            in_fence = stripped.startswith("```yaml") or stripped == "```yml"
            continue
        if not in_fence or not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("verification:"):
            in_verification = True
            continue

        # Leaving the block: a non-indented key ends it.
        if in_verification and line[:1] not in (" ", "\t"):
            in_verification = False

        if in_verification and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value in ("null", "~", ""):
                config[key] = None
            else:
                config[key] = value

    return config


def run_stage(command: str, cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired:
        return 124, "timed out after 900s"
    except OSError as exc:  # command not found, permission, etc.
        return 127, str(exc)

    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output


def main() -> int:
    root = find_project_root(Path.cwd().resolve())
    if root is None:
        print("VERIFY: NO CONFIG")
        print()
        print("No .claude/rules/verify.md found in this directory or any parent.")
        print("Run /harness:context-map to create one.")
        return 2

    config = parse_config(root / ".claude" / "rules" / "verify.md")
    if not config:
        print("VERIFY: NO CONFIG")
        print()
        print(f"Found {root / '.claude' / 'rules' / 'verify.md'} but no")
        print("`verification:` block inside a ```yaml fence.")
        return 2

    results: list[tuple[str, str]] = []
    failures: list[tuple[str, str]] = []
    gate_failed = False

    for stage in STAGES:
        if stage not in config:
            continue
        command = config[stage]

        if command is None:
            results.append((stage, "NOT CONFIGURED"))
            continue

        if gate_failed:
            results.append((stage, "SKIPPED (earlier gate failed)"))
            continue

        code, output = run_stage(command, root)
        if code == 0:
            results.append((stage, "PASS"))
        else:
            results.append((stage, f"FAIL (exit {code})"))
            failures.append((stage, output.strip()))
            gate_failed = True

    if RUNTIME_STAGE in config:
        cmd = config[RUNTIME_STAGE]
        note = "NOT RUN (long-lived process; verify manually or in a browser)"
        results.append((RUNTIME_STAGE, note if cmd else "NOT CONFIGURED"))

    width = max((len(name) for name, _ in results), default=0) + 1
    lines = [f"{name.upper() + ':':<{width + 1}} {verdict}" for name, verdict in results]
    block = "\n".join(lines)

    print(block)

    if failures:
        print()
        for stage, output in failures:
            print(f"--- {stage} raw output " + "-" * 40)
            if len(output) > MAX_OUTPUT:
                print(f"[truncated to last {MAX_OUTPUT} chars]")
                output = output[-MAX_OUTPUT:]
            print(output if output else "(no output)")

    # Persist for the Stop hook (Phase 3) and for humans.
    out_dir = root / "docs" / "context"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "last-verify.txt").write_text(block + "\n", encoding="utf-8")
    except OSError:
        pass  # never fail the run because we could not write a note

    return 1 if gate_failed else 0


if __name__ == "__main__":
    sys.exit(main())
