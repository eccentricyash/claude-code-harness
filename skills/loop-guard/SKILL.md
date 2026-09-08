---
name: "loop-guard"
description: "Set up a bounded autonomous loop with a machine-checkable exit criterion, an iteration cap, and a declared file scope. Use before running any repeated or self-directed task such as improving coverage, fixing a class of errors, or migrating files in bulk."
disable-model-invocation: true
argument-hint: "[goal]"
allowed-tools:
  - "Bash(python:*)"
  - "Read"
  - "Grep"
  - "Glob"
---

# loop-guard

Autonomy with a cage around it.

## Current contract

```!
python "${CLAUDE_SKILL_DIR}/scripts/contract.py" status 2>&1 || true
```

## The three preconditions

**Refuse to start without all three.** Do not infer them, do not pick sensible
defaults, do not proceed with two out of three. Ask the user.

| Precondition | Why | Bad | Good |
|---|---|---|---|
| **Exit command** — a shell command exiting 0 exactly when the goal is met | Without it the loop does not terminate, it gets interrupted. "It finished" and "I stopped it" are different outcomes and only an exit code distinguishes them. | "until coverage is good" | `npm test -- --coverage --coverageThreshold '{"global":{"lines":80}}'` |
| **Iteration cap** | Bounds the spend. 1–50. | "as many as it takes" | `--max-iterations 12` |
| **File scope** | Turns scope creep into a stop condition rather than a surprise | "the auth code" | `src/auth/*.ts src/auth/*.test.ts` |

If the user's goal cannot be expressed as a command that exits 0, **the goal is
not ready to automate.** Say so and help them make it checkable — usually a
test, a lint rule, or a grep that must return nothing. That conversation is the
valuable part of this skill.

## Arming it

```
python "${CLAUDE_SKILL_DIR}/scripts/contract.py" init \
  --goal "$ARGUMENTS" \
  --exit-command "<command>" \
  --max-iterations <n> \
  --scope <files...>
```

`init` also **executes the exit command once** to prove it runs. A criterion
with a typo never returns 0, so the loop would burn its whole budget and then
report failure — the most expensive way to discover a mistake.

## Each iteration

```
python "${CLAUDE_SKILL_DIR}/scripts/contract.py" check
```

It returns `CONTINUE` or `STOP`, and names the tier:

| Tier | When | Checks |
|---|---|---|
| **iteration** | every round | Exit command + `tree-check` against scope. Targeted tests only. |
| **milestone** | every 5th | Full `/harness:verify` |
| **stopping** | goal met or cap hit | Full `verify`, then `ship-check` |

**Do not run the full chain every iteration.** Twenty rounds of typecheck →
lint → test → build is quota destruction, and it is the reason people abandon
gated loops.

## Rules while looping

1. **`STOP` means stop.** Do not re-arm with a higher cap to keep going. Hitting
   the cap is a *failure*, not a completion — report what was attempted and what
   remains, and let the user decide.
2. **Anything outside scope is a stop condition**, not a warning. If the work
   genuinely needs a file outside scope, stop and re-arm with the wider scope
   stated explicitly.
3. **Never edit the exit command mid-loop.** Moving the goalposts to make a loop
   succeed produces a green result that means nothing.
4. **Report per iteration**: what changed, what the criterion said, tier run.
   A loop nobody can audit afterwards is not bounded, only unattended.
5. **A passing exit criterion is not "done".** It is one measurement. Run
   `verify` and `ship-check` before saying the work is finished.

## Composition, not reimplementation

This skill does not implement looping. Claude Code already has `/loop`, and
`ralph-loop` exists if you want a Stop-hook driven variant. `loop-guard`
supplies the **contract** those run inside: the exit condition, the cap, the
scope, and the tiering.

Drive it manually, or hand the `check` command to `/loop`. Either way the
contract is what makes the loop bounded.
