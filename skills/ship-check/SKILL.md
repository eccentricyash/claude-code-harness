---
name: "ship-check"
description: "Pre-release gate: run security scanners, then walk the security, accessibility and auth checklists that scanners cannot cover. Use before shipping, deploying, opening a release PR, or when asked whether something is safe to launch."
disable-model-invocation: true
allowed-tools:
  - "Bash(python:*)"
  - "Bash(gitleaks:*)"
  - "Bash(npm audit:*)"
  - "Bash(pip-audit:*)"
  - "Bash(semgrep:*)"
  - "Bash(git log:*)"
  - "Bash(git diff:*)"
  - "Read"
  - "Grep"
  - "Glob"
---

# ship-check

The release gate. Deterministic scanners, then the judgement calls no scanner
makes.

## 1. Scanners

```!
python "${CLAUDE_SKILL_DIR}/scripts/scan.py" 2>&1 || true
```

**`NOT INSTALLED` is not a pass.** Say plainly which scanners did not run. A
checklist that omits the checks you do not have is how people come to believe
they ran them.

## 2. Checklists

Load only what applies to this change — these are large, and loading all three
for a backend-only change is wasted context:

| Reference | Load when |
|---|---|
| [security-20.md](references/security-20.md) | **always** |
| [a11y.md](references/a11y.md) | any user-facing UI changed |
| [auth.md](references/auth.md) | login, sessions, passwords, tokens, or permissions changed |

## 3. Reporting

Every item is classified. Report by classification, because the confidence you
can offer differs by class:

| Class | Meaning | What you may claim |
|---|---|---|
| **AUTOMATED** | A tool produced a verdict | "Checked — clean" or "Found: …" |
| **SEMI** | A defined procedure with an expected result | Only what you actually observed |
| **MANUAL** | Requires reasoning about intent | "Needs review" plus your assessment, never "passed" |

Rules:

1. **Never report a MANUAL item as passing.** You cannot verify authorization
   or business logic by reading code alone. State what you found and what you
   could not determine.
2. **Attach evidence for SEMI items.** The reference names the expected
   evidence for each. Without it, the item is unchecked, not passed.
3. **Do not fix anything in this turn.** This is a gate. Report, then let the
   user decide what to fix and in what order.
4. **Rank findings by blast radius**, not by how many you found. One
   authorization hole outranks twenty dependency advisories.
5. **Scope to the change** unless asked for a full audit. A release gate on a
   copy tweak should not re-audit the whole codebase.

## 4. Summary shape

```
SCANNERS
  <verdict per scanner, and which did not run>

BLOCKERS         (do not ship)
  - <finding, file:line, what an attacker or user gets>

NEEDS REVIEW     (MANUAL items, ranked)
  - <item> - what I checked, what I could not determine

CLEARED
  - <what was actually verified, with how>

NOT CHECKED
  - <items skipped, and why>
```

`NOT CHECKED` is mandatory when anything was skipped. An honest gap is useful;
a silent one is how a checklist becomes theatre.

## The honest split

Roughly half of the twenty items are catchable by tooling. The rest —
authorization, tenancy, guessable identifiers, what the business logic actually
permits — need a person. That ratio shifts with stack and tooling, but the
distinction does not: **scanners find pattern and dependency problems; only
reasoning finds authorization and business-logic problems.**

Say so in the summary. A gate that implies more coverage than it has is worse
than no gate.
