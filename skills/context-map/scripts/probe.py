#!/usr/bin/env python3
"""Probe a repository and report what a verification chain could actually run.

Discovery, not assumption. The point is to find the commands this project really
has, so /harness:verify runs real ones instead of guessing `npm test` at a repo
that uses pytest.

Prints a findings report for the model to turn into .claude/rules/verify.md.
Exits 0 always -- this is a read-only report, never a gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

MAX_WORKSPACES = 12


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def detect_package_manager(root: Path) -> str:
    for lockfile, manager in (
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"),
        ("package-lock.json", "npm"),
    ):
        if (root / lockfile).is_file():
            return manager
    return "npm"


def section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def probe_node(root: Path) -> None:
    pkg_path = root / "package.json"
    if not pkg_path.is_file():
        return

    pkg = read_json(pkg_path)
    scripts = pkg.get("scripts", {}) or {}
    manager = detect_package_manager(root)

    section(f"Node project ({manager})")
    if not scripts:
        print("package.json has no scripts block.")
    else:
        print("Available scripts:")
        for name, cmd in sorted(scripts.items()):
            print(f"  {name:<16} {cmd}")

    run = f"{manager} run" if manager != "npm" else "npm run"
    print()
    print("Candidate mapping:")
    for stage, names in (
        ("typecheck", ["typecheck", "type-check", "tsc", "types"]),
        ("lint", ["lint", "eslint"]),
        ("test", ["test", "test:unit", "vitest", "jest"]),
        ("build", ["build", "compile"]),
        ("run", ["dev", "start", "serve"]),
    ):
        hit = next((n for n in names if n in scripts), None)
        if hit:
            prefix = f"{manager} " if hit == "test" and manager != "npm" else f"{run} "
            print(f"  {stage:<10} {prefix}{hit}")
        else:
            print(f"  {stage:<10} null   # no matching script")

    workspaces = pkg.get("workspaces")
    if workspaces:
        print()
        print(f"Workspaces declared: {workspaces}")
        print("This is a monorepo -- per-package commands may be needed.")


def probe_python(root: Path) -> None:
    pyproject = root / "pyproject.toml"
    has_reqs = (root / "requirements.txt").is_file()
    if not pyproject.is_file() and not has_reqs:
        return

    section("Python project")
    text = pyproject.read_text(encoding="utf-8", errors="replace") if pyproject.is_file() else ""

    tools = {
        "ruff": "ruff" in text or (root / "ruff.toml").is_file(),
        "mypy": "mypy" in text or (root / "mypy.ini").is_file(),
        "pytest": "pytest" in text or (root / "pytest.ini").is_file() or (root / "tests").is_dir(),
        "poetry": "[tool.poetry]" in text,
        "uv": (root / "uv.lock").is_file(),
    }
    for name, present in tools.items():
        print(f"  {name:<10} {'found' if present else '-'}")

    print()
    print("Candidate mapping:")
    print(f"  typecheck  {'mypy .' if tools['mypy'] else 'null   # no mypy config'}")
    print(f"  lint       {'ruff check .' if tools['ruff'] else 'null   # no ruff config'}")
    print(f"  test       {'pytest' if tools['pytest'] else 'null   # no tests found'}")
    print("  build      null   # set if this package is published")


def probe_other(root: Path) -> None:
    found = []
    for name, note in (
        ("Makefile", "check targets: make test / make lint"),
        ("docker-compose.yml", "Docker-only startup -- `run` may be `docker compose up`"),
        ("compose.yaml", "Docker-only startup"),
        ("Cargo.toml", "Rust: cargo check / cargo clippy / cargo test / cargo build"),
        ("go.mod", "Go: go vet / go test ./... / go build ./..."),
        (".github/workflows", "CI workflows -- the most reliable source of real commands"),
    ):
        if (root / name).exists():
            found.append((name, note))

    if found:
        section("Other signals")
        for name, note in found:
            print(f"  {name:<24} {note}")


def probe_git(root: Path) -> None:
    section("Repository")
    print(f"  root            {root}")
    print(f"  git repo        {'yes' if (root / '.git').exists() else 'NO'}")
    print(f"  .gitignore      {'yes' if (root / '.gitignore').is_file() else 'NO'}")
    existing = root / ".claude" / "rules" / "verify.md"
    verify_state = "EXISTS -- will be overwritten" if existing.is_file() else "absent"
    print(f"  verify.md       {verify_state}")
    print(f"  CLAUDE.md       {'exists' if (root / 'CLAUDE.md').is_file() else 'absent'}")


def main() -> int:
    root = Path.cwd().resolve()
    # ASCII only: Windows consoles default to cp1252 and mangle box-drawing
    # characters and dashes into replacement chars.
    print(f"CONTEXT-MAP PROBE - {root.name}")

    probe_git(root)
    probe_node(root)
    probe_python(root)
    probe_other(root)

    section("Reminder")
    print("These are candidates, not facts. Confirm each command actually runs")
    print("before writing it into verify.md -- a chain of commands that error out")
    print("is worse than an honest `null`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
