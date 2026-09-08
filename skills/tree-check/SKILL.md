---
name: "tree-check"
description: "List every file changed in the working tree, including untracked additions, and flag anything outside a declared scope. Use after implementing a change, before committing, or when asked what was actually modified or whether anything unexpected changed."
argument-hint: "[expected files, space separated]"
allowed-tools:
  - "Bash(python:*)"
  - "Bash(git status:*)"
  - "Bash(git diff --stat:*)"
  - "Read"
---

# tree-check

Catch the failure class tests cannot see: a file changed that nobody asked for.

## Run it

```!
python "${CLAUDE_SKILL_DIR}/scripts/tree_check.py" $ARGUMENTS 2>&1 || true
```

## How to report it

1. **`TREE-CHECK: FAIL` means unexpected files changed.** Name each one and say
   what it was. Do not wave it through as "just a lockfile" — say that it is a
   lockfile and let the user decide.
2. **Untracked additions matter most.** A file the agent created outside the
   plan is the exact thing this gate exists for. `git diff` cannot see these;
   that is why this uses `--porcelain`.
3. **Declared-but-untouched is a real signal too.** If the plan said a file
   would change and it did not, either the plan was wrong or the work is
   incomplete. Say which you think it is.
4. **State the blind spot when it is relevant.** Gitignored paths are not
   reported by default. If the change plausibly wrote into `dist/`, `.next/`,
   or `node_modules/`, re-run with `--ignored` rather than assuming it did not.
5. **Never "fix" scope drift by deleting files.** Report it. Deleting someone's
   work to make a gate pass is the worst possible response to this signal.

## Passing an expected list

Without arguments it lists everything that changed. With arguments it compares
against a declared scope:

```
/harness:tree-check src/auth/session.ts src/auth/session.test.ts
```

Take the expected list from the plan you are working to. If there is no
declared scope, run it bare and report what changed rather than inventing an
expectation to measure against.
