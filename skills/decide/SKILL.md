---
name: "decide"
description: "Record an architectural decision as a numbered ADR in docs/decisions and refresh docs/context/progress.md. Use after choosing between approaches, picking a library, settling a tradeoff, or when asked to write this down or remember why we did it this way."
argument-hint: "[what was decided]"
allowed-tools:
  - "Bash(ls docs/decisions:*)"
  - "Bash(git log:*)"
  - "Read"
  - "Write"
  - "Edit"
---

# decide

Decisions live longer than context windows. This writes them somewhere
compaction cannot reach.

## Existing decisions

```!
ls -1 docs/decisions 2>/dev/null | tail -5 || echo "(no docs/decisions yet)"
```

## What to do

1. **Pick the next number.** Look at the listing above; use `0001` if empty.
   Filename is `docs/decisions/NNNN-kebab-slug.md`.

2. **Write the ADR** using the template below. Keep it short — an ADR nobody
   rereads is wasted effort. Four sentences per section is plenty.

3. **Update `docs/context/progress.md`** — create it if missing. This is
   execution state, overwritten each time, and it is a different thing from an
   ADR: decisions are append-only history, progress is where you are right now.

4. **Do not invent the rationale.** Record what was actually decided and why,
   from this conversation. If the "why" was never discussed, write
   `Rationale: not captured` rather than a plausible-sounding reconstruction. A
   fabricated rationale is worse than a missing one, because later you will
   believe it.

## ADR template

```markdown
# NNNN — <decision, stated as a fact>

- **Date:** YYYY-MM-DD
- **Status:** accepted

## Context

What forced a decision. The constraint, bug, or requirement.

## Options considered

- **<option>** — why it was or was not chosen.
- **<option>** — same.

## Decision

What we are doing, in one or two sentences.

## Consequences

What this makes easy, what it makes hard, and what would make us revisit it.
```

## progress.md template

```markdown
# Progress

**Objective:** <the current goal, one line>

- **Done:** <completed, briefly>
- **In progress:** <what is being worked on now>
- **Blocked:** <what is stuck and on what, or "nothing">
- **Next:** <the single next action>
- **Last verification:** <paste the latest verify block, or "not run">

_Updated: YYYY-MM-DD_
```

Keep `progress.md` under ~20 lines. If it grows past that it has become the
sprawl it was meant to prevent — prune it.
