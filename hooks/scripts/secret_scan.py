#!/usr/bin/env python3
"""Shared secret detection for the write and shell guards.

Design note: false positives are the real failure mode here. A guard that
blocks legitimate work -- test fixtures, docs examples, mock credentials --
gets bypassed, and then you have trained yourself past your own control. So
this uses entropy scoring rather than bare prefix matching, and honours an
explicit allowlist.

Config lives in hooks/allowlist.json. JSON rather than TOML deliberately:
tomllib is 3.11+, and a hook that crashes on an older interpreter is a control
you believe you have and do not.
"""
from __future__ import annotations

import fnmatch
import json
import math
import re
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "allowlist.json"

DEFAULTS = {
    "paths": [
        "**/tests/fixtures/**",
        "**/test/fixtures/**",
        "**/*.example",
        "**/*.example.*",
        "**/*.sample",
        "**/docs/**/*.md",
        "**/*.test.*",
        "**/*.spec.*",
    ],
    "pragma": "gitleaks:allow",
    "known_examples": [
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "sk-test",
        "sk-ant-test",
        "ghp_test",
        "xxxxxxxx",
        "your-api-key",
        "YOUR_API_KEY",
        "changeme",
        "placeholder",
        "0123456789abcdef",
    ],
    "entropy_threshold": 4.2,
    "min_secret_length": 20,
}

# Always fatal, entropy irrelevant.
HARD_PATTERNS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key block"),
]

# Provider-issued credential prefixes. Still checked against the allowlist.
PREFIX_PATTERNS = [
    (re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic API key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "OpenAI-style API key"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs)_[A-Za-z0-9]{30,}"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}"), "GitHub fine-grained PAT"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}"), "Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "Google API key"),
    (re.compile(r"\bey[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"), "JWT"),
]

# name = "high entropy value"
ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(\w*(?:secret|passwd|password|token|api[_-]?key|access[_-]?key|
        private[_-]?key|credential|auth)\w*)
    \s*[:=]\s*
    ['"]?([A-Za-z0-9+/=_\-]{%d,})['"]?
    """
    % DEFAULTS["min_secret_length"]
)

# .env, .env.local, .env.production -- but NOT .env.example and friends, which
# are templates, contain placeholders, and are meant to be committed.
ENV_FILE = re.compile(r"(^|[\\/])\.env(\.|$)")
ENV_TEMPLATE = re.compile(
    r"(^|[\\/])\.env\.(example|sample|template|dist|defaults?)$", re.I
)


def load_config() -> dict:
    config = dict(DEFAULTS)
    try:
        config.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass  # defaults are safe; never fail closed on a malformed allowlist
    return config


def shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts: dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    length = len(value)
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


def path_allowed(path: str, config: dict) -> bool:
    """Match a path against allowlist globs.

    fnmatch's `*` already spans `/`, but a leading `**/` still needs a segment
    before it -- so `**/tests/fixtures/**` fails to match a path that *starts*
    with `tests/`. Try the bare form too, and an absolute-ish variant.
    """
    if not path:
        return False
    norm = path.replace("\\", "/").lstrip("./")

    for pat in config["paths"]:
        candidates = {pat}
        if pat.startswith("**/"):
            candidates.add(pat[3:])
        for candidate in candidates:
            if fnmatch.fnmatch(norm, candidate) or fnmatch.fnmatch("/" + norm, candidate):
                return True
    return False


def _is_known_example(value: str, config: dict) -> bool:
    low = value.lower()
    return any(ex.lower() in low for ex in config["known_examples"])


def scan(content: str, path: str = "", config: dict | None = None) -> list[str]:
    """Return a list of human-readable findings. Empty means clean."""
    config = config or load_config()

    if path_allowed(path, config):
        return []

    findings: list[str] = []
    pragma = config["pragma"]
    threshold = float(config["entropy_threshold"])

    for lineno, line in enumerate(content.splitlines(), 1):
        if pragma in line:
            continue

        for pattern, label in HARD_PATTERNS:
            if pattern.search(line):
                findings.append(f"line {lineno}: {label}")

        for pattern, label in PREFIX_PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(0)
                if _is_known_example(value, config):
                    continue
                findings.append(f"line {lineno}: {label} ({value[:12]}...)")

        for match in ASSIGNMENT.finditer(line):
            name, value = match.group(1), match.group(2)
            if _is_known_example(value, config):
                continue
            if shannon_entropy(value) < threshold:
                continue
            entropy = shannon_entropy(value)
            findings.append(
                f"line {lineno}: high-entropy value assigned to '{name}' "
                f"(entropy {entropy:.1f} >= {threshold})"
            )

    return findings


def is_env_file(path: str) -> bool:
    """True for a real env file. Templates (.env.example) are not secrets."""
    norm = (path or "").replace("\\", "/")
    if ENV_TEMPLATE.search(norm):
        return False
    return bool(ENV_FILE.search(norm))
