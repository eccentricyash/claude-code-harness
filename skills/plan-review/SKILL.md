---
name: "plan-review"
description: "Attack a plan before any code is written, using a fresh read-only reviewer that checks it against the real repository. Use before implementing anything risky, or when asked to review, sanity-check, or poke holes in a plan or approach."
disable-model-invocation: true
context: fork
agent: adversary
background: false
argument-hint: "[path to plan, or paste the plan]"
---

# plan-review

Catch the expensive failure: a plan that reads as coherent but is wrong.

## What to review

$ARGUMENTS

If no argument was given, review the plan most recently discussed in this
conversation. If there is no plan, say so and stop — do not invent one to
review.

## Instructions

You are running as the `adversary` agent: a **fresh context** with `Read`,
`Grep`, and `Glob`, and no ability to edit. Use that.

1. **Verify every concrete claim against the repository.** File paths,
   function names, script names, config keys, package names. A plan that
   references code which does not exist is the most common and cheapest defect
   to find, and you are the only step that will catch it before implementation.
2. **Search for prior art** before accepting that something needs building.
   `Grep` for the behaviour. If it already exists, that is a blocker with a
   path attached.
3. **Name the load-bearing assumption** — the one that, if false, makes the
   rest pointless.
4. **Ask what proves it worked.** No verification path is a blocker.
5. **Ask what happens if it fails halfway.**

Output in the exact shape defined in your agent instructions: `VERDICT`,
`BLOCKERS`, `ASSUMPTIONS`, `MISSING VERIFICATION`, `ROLLBACK`.

## Honesty requirements

- **`VERDICT: PASS` with nothing found is a valid, expected outcome.** Do not
  manufacture concerns to look thorough. A review that always finds something
  trains people to skip reviews.
- **`FAIL` requires at least one real blocker.** Style, naming, and ordering
  are not blockers.
- **Do not rewrite the plan.** Name the defect; the author picks the fix.

## What this does not give you

A fresh context reduces correlated failure. It does **not** create
independence — same model family, same repository, overlapping blind spots.
Treat a `PASS` as "no obvious defect found by one more careful look", never as
proof the plan is correct. The deterministic gates (`verify`, `tree-check`,
scanners) are the real backstop.
