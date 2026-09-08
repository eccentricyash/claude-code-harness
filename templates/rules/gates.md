# Gates — which checks run for which changes

Gates are proportional to blast radius. A harness that runs five checks on a
typo is a speed limiter, and a speed limiter gets switched off.

Classification is by path and keyword glob so it is **declared and
deterministic** — not a mode anyone has to remember to flip.

## Trivial — no gates

Ship it.

```
**/*.md
docs/**
**/*.txt
.github/ISSUE_TEMPLATE/**
```

Also trivial regardless of path: comment-only edits, formatting-only changes,
and copy changes in user-facing strings that carry no logic.

## Standard — verify, then tree-check

The default for real work.

```
src/**
lib/**
app/**
components/**
tests/**
```

## Risky — the full loop

`plan-review` → implement → `verify` → `tree-check` → `/code-review` →
`ship-check` → `decide`

```
**/auth/**
**/*auth*
**/middleware.*
**/migrations/**
**/schema.*
**/*.sql
**/rls/**
**/policies/**
**/payment*/**
**/billing/**
**/webhook*/**
**/api/**
package.json
package-lock.json
pnpm-lock.yaml
requirements.txt
pyproject.toml
.claude/**
.github/workflows/**
Dockerfile
docker-compose*
```

Risky by nature regardless of path:

- Anything touching authentication, authorization, or session handling
- Anything that changes what data leaves the system
- Dependency additions or upgrades
- Anything that changes CI, permissions, or the harness itself

## Calibration

If nearly everything lands in **risky**, the globs are wrong and you will start
skipping gates — which is worse than not having them. If nearly everything
lands in **trivial**, they are not protecting anything.

Rough target for a healthy project: **~20% trivial, ~65% standard, ~15% risky.**
Track the real distribution in `docs/metrics.md` and re-tune quarterly.

## Escalation

Any single one of these promotes a change to the next tier up:

- It touches a file listed under a higher tier
- It is a dependency change
- The diff exceeds ~300 lines
- You cannot state what would break if it is wrong
