# Compatibility

This harness composes Claude Code primitives, so it drifts when they change.
The CLI is deliberately **not pinned** — `autoUpdatesChannel: latest` is right
for a daily driver. Instead: record what it was tested against, expect drift,
and let CI catch it.

```yaml
tested_with:
  claude_code: 2.1.263
  platform: win32-x64
  shell: PowerShell (primary), Git Bash (secondary)
  python: 3.x on PATH
  model: claude-opus-5 (1M context)
last_verified: 2026-09-08
```

## Behaviour this depends on

Each row is something that could change under us. If a skill starts
misbehaving after an update, check here first.

| Depends on | Where | Breaks if |
|---|---|---|
| Skills-directory plugins auto-load as `<name>@skills-dir` | whole repo | the feature is renamed or requires an install step |
| `${CLAUDE_SKILL_DIR}` resolves in `!` blocks and `allowed-tools` | `verify`, `tree-check`, `context-map` | variable renamed |
| An injected `!` command exiting non-zero **aborts the skill** | `verify`, `tree-check` — both use `\|\| true` | behaviour changes; the guard becomes redundant but harmless |
| `skillListingBudgetFraction` defaults to 1% of the window | the sizing argument in README | default changes; re-measure and update the table |
| Read/Edit deny rules use gitignore syntax with `//` as filesystem-root anchor | Layer 0 settings | anchor semantics change — **re-run the four `.env` fixtures immediately** |
| Read deny rules also cover Bash read commands | Layer 0 settings | a `cat` bypass appears; the floor becomes decorative |
| `git status --porcelain` reports untracked as `??` and ignored as `!!` | `tree-check` | git output format changes |
| Skill usage stats live in `/plugin` → **Stats** tab | the monthly eviction rule | moves again (it was `/skill-doctor` before 2.1.263) |

## Known moved/renamed

| Was | Now | Noticed |
|---|---|---|
| `/skill-doctor` | `/plugin` → Stats tab | 2.1.263 |

## After a Claude Code update

1. `claude plugin validate ~/.claude/skills/harness --strict`
2. Re-run the `.env` deny fixtures — including the Bash `cat` case
3. `/context` and `/plugin` → Stats; append a row to `docs/metrics.md`
4. Update `tested_with` above
