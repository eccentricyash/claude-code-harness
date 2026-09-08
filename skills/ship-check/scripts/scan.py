#!/usr/bin/env python3
"""Run whatever deterministic security scanners are actually installed.

Reports NOT INSTALLED rather than silently skipping. A checklist that quietly
omits the checks you do not have is how you end up believing you ran them.

Every verdict here comes from a scanner's exit code. The judgement calls --
authorization, business logic, whether an ID is guessable -- are not in this
file, because no scanner answers them. Those live in references/security-20.md
and are marked MANUAL.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT = 300


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT
        )
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {TIMEOUT}s"
    except OSError as exc:
        return 127, str(exc)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def find_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / ".git").exists():
            return d
    return start


def scan_secrets(root: Path) -> tuple[str, str]:
    if not have("gitleaks"):
        return "NOT INSTALLED", "install: https://github.com/gitleaks/gitleaks"
    code, out = run(["gitleaks", "detect", "--no-banner", "--redact"], root)
    if code == 0:
        return "CLEAN", ""
    return "FINDINGS", out.strip()[-2000:]


def scan_node_deps(root: Path) -> tuple[str, str]:
    if not (root / "package.json").is_file():
        return "N/A", "no package.json"
    if not have("npm"):
        return "NOT INSTALLED", "npm not on PATH"
    code, out = run(
        ["npm", "audit", "--omit=dev", "--audit-level=high", "--json"], root
    )
    try:
        data = json.loads(out)
        meta = data.get("metadata", {}).get("vulnerabilities", {})
        high = meta.get("high", 0)
        critical = meta.get("critical", 0)
        if high or critical:
            return "FINDINGS", f"{critical} critical, {high} high"
        return "CLEAN", "no high or critical advisories"
    except ValueError:
        return ("CLEAN", "") if code == 0 else ("FINDINGS", out.strip()[-1000:])


def scan_python_deps(root: Path) -> tuple[str, str]:
    markers = ["pyproject.toml", "requirements.txt"]
    if not any((root / m).is_file() for m in markers):
        return "N/A", "no Python dependency manifest"
    if not have("pip-audit"):
        return "NOT INSTALLED", "install: pip install pip-audit"
    code, out = run(["pip-audit", "--strict"], root)
    return ("CLEAN", "") if code == 0 else ("FINDINGS", out.strip()[-2000:])


def scan_sast(root: Path) -> tuple[str, str]:
    if not have("semgrep"):
        return "NOT INSTALLED", "install: pip install semgrep"
    code, out = run(["semgrep", "--config", "auto", "--error", "--quiet"], root)
    return ("CLEAN", "") if code == 0 else ("FINDINGS", out.strip()[-3000:])


CHECKS = [
    ("SECRETS      (gitleaks)", scan_secrets),
    ("DEPS-NODE    (npm audit)", scan_node_deps),
    ("DEPS-PYTHON  (pip-audit)", scan_python_deps),
    ("SAST         (semgrep)", scan_sast),
]


def main() -> int:
    root = find_root(Path.cwd().resolve())
    print(f"SHIP-CHECK SCAN - {root.name}")
    print()

    results = []
    details = []
    for label, fn in CHECKS:
        verdict, detail = fn(root)
        results.append((label, verdict))
        if detail and verdict in ("FINDINGS", "NOT INSTALLED"):
            details.append((label, verdict, detail))

    for label, verdict in results:
        print(f"{label}: {verdict}")

    for label, verdict, detail in details:
        print()
        print(f"--- {label.strip()} [{verdict}] " + "-" * 30)
        print(detail)

    findings = sum(1 for _, v in results if v == "FINDINGS")
    missing = sum(1 for _, v in results if v == "NOT INSTALLED")

    print()
    print(f"SCANNERS: {findings} with findings, {missing} not installed")
    if missing:
        print("A scanner you do not have is not a scanner that passed.")
    print()
    print("Automated scanning covers roughly half of the checklist. The")
    print("authorization and business-logic items need a human; see")
    print("references/security-20.md, section MANUAL.")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
