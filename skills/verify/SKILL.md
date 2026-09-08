---
name: "verify"
description: "Run this project's declared verification chain (typecheck, lint, test, build) and report the result. Use when asked to verify, check, or confirm that changes work, before committing, or after finishing an implementation. Reports exit codes; never claims success on its own."
disable-model-invocation: false
allowed-tools:
  - "Bash(python:*)"
  - "Bash(py -3:*)"
  - "Bash(python3:*)"
  - "Read"
---

# verify

Run the project's verification chain and report exactly what happened.

## Run it

```!
python "${CLAUDE_SKILL_DIR}/scripts/run_verify.py" 2>&1 || true
```

`|| true` is load-bearing: an injected command that exits non-zero **aborts the
skill invocation**, and this script exits 1 by design when a gate fails. The
verdict lives in the text block, not the exit status.

## Rules for reporting the result above

**You do not determine PASS or FAIL.** Every verdict in that block came from a
process exit code. Report it; never override it.

1. **Lead with the block, verbatim.** Do not reformat, summarize away, or
   "interpret" a verdict. If it says `TEST: FAIL`, the tests failed.
2. **Never claim success when any line reads FAIL.** Not "mostly passing", not
   "just a flaky test" — unless you have re-run it and have a new block showing
   PASS.
3. **Do not fix anything in this turn.** Report, then stop. Fixing is a separate
   turn with the user's go-ahead. A verifier that repairs what it measures is
   not a verifier.
4. **For each failure**, quote the relevant lines of raw output and name the
   file and line if the output gives them. Do not paste the whole dump.
5. **`NOT CONFIGURED` is a finding, not a pass.** It means the project declared
   that stage as `null`. Say so plainly — a missing test suite should be
   visible.
6. **`VERIFY: NO CONFIG`** means there is no `.claude/rules/verify.md`. Say that
   and offer `/harness:context-map`. Do not guess at commands and run them.

## What good output looks like

> ```
> TYPECHECK: PASS
> LINT:      PASS
> TEST:      FAIL (exit 1)
> BUILD:     SKIPPED (earlier gate failed)
> RUN:       NOT RUN (long-lived process; verify manually or in a browser)
> ```
>
> Tests failed — 3 assertions in `auth.spec.ts`, all on the session-expiry path
> (lines 44, 51, 63). Build was not attempted because the test gate failed.
> Want me to fix them?
