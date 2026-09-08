---
name: "context-map"
description: "Bootstrap a project's Claude Code spine: discover its real build and test commands, then write CLAUDE.md, .claude/rules/verify.md, .claude/rules/gates.md and docs/decisions. Use when setting up a new repository, onboarding a project, or when verify reports no config."
disable-model-invocation: true
allowed-tools:
  - "Bash(python:*)"
  - "Read"
  - "Write"
  - "Glob"
  - "Grep"
---

# context-map

Set up layer 3 for a repository. Run once per project.

## Probe

```!
python "${CLAUDE_SKILL_DIR}/scripts/probe.py" 2>&1 || true
```

## What to write

Use the probe above, then **confirm before you commit to anything**. The probe
reports candidates; a command that does not actually run is worse than an
honest `null`, because `verify` will report a failure that is really a typo.

### 1. `.claude/rules/verify.md`

```markdown
# Verification chain

```yaml
verification:
  typecheck: <command or null>
  lint:      <command or null>
  test:      <command or null>
  build:     <command or null>
  run:       <command or null>
trust: authored          # authored | reviewed | untrusted
tree_check_ignored: false
```
```

Rules:
- **Write `null` explicitly** for anything the project lacks. Never invent a
  command so the chain looks complete. A missing test suite must be *visible*.
- **Verify each command runs** before writing it. Run it once.
- `run` is never executed by `verify` — it is recorded so a human knows how to
  start the thing.
- `trust: untrusted` for a repo you did not write. It signals that scans should
  happen in a sandbox rather than in-session.

### 2. `.claude/rules/gates.md`

Copy `${CLAUDE_PLUGIN_ROOT}/templates/rules/gates.md` and adjust the globs to
this repo's real layout. This is what keeps the harness from running five gates
on a typo.

### 3. `CLAUDE.md` — 80 lines maximum

This is loaded **every turn, forever**. It gets exactly four things:

1. What this project is — two sentences.
2. How to run it.
3. How to verify it.
4. The **five** rules that are actually violated in practice here.

It does **not** get: the file tree (Claude can read it), the git history (git
has it), aspirations, or style guidance nobody checks. If you are tempted to
add a sixth rule, replace a weaker one instead.

### 4. `docs/decisions/` and `docs/context/`

Create both directories with a `.gitkeep`. `/harness:decide` fills them.

### 5. `.claude/settings.local.json`

Allow-list the exact commands from `verify.md` so daily work stops prompting:

```json
{
  "permissions": {
    "allow": ["Bash(npm run lint)", "Bash(npm test)"]
  }
}
```

**Exact commands only — never a wildcard like `Bash(npm:*)` or `Bash(pnpm *)`.**
A broad package-manager rule permits `install`, `add`, and `dlx`, which executes
arbitrary remote packages. Allow-lists belong here, in project scope, and never
in user settings.

Add `.claude/settings.local.json` to `.gitignore` — it is your convenience, not
team policy.

## Finally

Report what you wrote, and **name anything you set to `null`**. An unverifiable
project is a finding worth stating out loud, not a detail to bury.
