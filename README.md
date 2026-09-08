# harness

A thin control layer over Claude Code's native primitives.

**Not another agent framework.** Claude Code already provides on-demand skill
loading, deferred MCP schemas, isolated subagent contexts, deterministic
permission rules, blocking hooks, and OS sandboxing. This composes those into
one engineering loop and reimplements none of them.

Six skills, two agents, two hooks. That is the whole thing, and the smallness
is the design — not a limitation of it.

---

## Why it is small

Every skill's one-line description sits in the system prompt **on every turn**.
Claude Code budgets that listing at `skillListingBudgetFraction`, default **1%
of the model's context window**, and when the budget is exceeded it **drops
descriptions starting with the least-used skills**. You do not get an error.
You get non-determinism about which of your capabilities exist this turn.

Measured on the machine this was built on — Claude Code 2.1.263, Opus 5, 1M
context:

| | tokens | % of budget |
|---|---|---|
| Budget (1% of 1M) | ~10,000 | 100% |
| 18 built-in skills | 2,900 | 29% |
| + this harness (6 skills) | ~1,100 | → 39% |
| A 286-skill catalogue | ~46,000 | **460%** |

That last row is why this repo is not a mega-bundle. Four-and-a-half times over
budget guarantees truncation, and it is a *conservative* estimate.

Full `SKILL.md` bodies are **not** loaded every turn — only the listing. The
cost of a large catalogue is discovery ambiguity and silent truncation, not raw
body tokens. Getting that argument right matters; the sloppy version of it is
wrong.

---

## The loop

Gates are proportional to blast radius, declared as globs in
`.claude/rules/gates.md`. A harness that runs five checks on a typo is a speed
limiter, and a speed limiter gets switched off.

| Class | Examples | Gates |
|---|---|---|
| **Trivial** | docs, comments, formatting | none |
| **Standard** | most feature work | `verify` → `tree-check` |
| **Risky** | auth, schema, migrations, deps, CI, `.claude/**` | full loop |

```
FRAME → PLAN → PLAN-REVIEW → IMPLEMENT → VERIFY → TREE-CHECK → CODE-REVIEW → SHIP-CHECK → DECIDE
                    │                        │         │                          │          │
             fresh, read-only          exit codes,  expected               deterministic  durable
                 adversary            not opinions  files only             + LLM security  memory
```

---

## Skills

| Skill | What it does |
|---|---|
| `/harness:verify` | Runs the project's declared chain. **Emits PASS/FAIL from process exit codes** — the model reports, it never decides. |
| `/harness:tree-check` | Lists every changed file **including untracked ones**, flags anything outside declared scope. |
| `/harness:context-map` | Probes a repo for its real commands, writes `CLAUDE.md`, `verify.md`, `gates.md`. |
| `/harness:decide` | Appends a numbered ADR; refreshes `progress.md`. Memory that outlives the context window. |
| `/harness:plan-review` | *(Phase 3)* Fresh read-only adversary attacks a plan before code exists. |
| `/harness:ship-check` | *(Phase 3)* Release gate: scanners plus the checks scanners cannot do. |

---

## The design principle

Use the strongest mechanism appropriate to the property. These are layers, not
alternatives:

| Property | Mechanism | Why |
|---|---|---|
| Access policy | `permissions.deny` / `ask` | Applies immediately, independent of hooks |
| Deterministic runtime checks | Hooks, exit code 2 | Outside model context, zero tokens, cannot be argued with |
| Containment of untrusted code | OS sandbox | The only real boundary when the repo may be hostile |
| Workflow and judgment | Skills, agents, rules | Guidance — **never** rely on these for security |

Corollary: `verify` is a **script**, not a prompt. Instructions can be
rationalised around; an exit code cannot.

---

## Known limitations

Stated because a harness whose failure modes you cannot name is a harness you
do not understand.

| Limitation | Consequence | Mitigation |
|---|---|---|
| **`verify` narration is not enforced** | The block is deterministic; the sentence describing it is not. A model *could* misreport a FAIL. | `Stop` hook injects the raw result beside the claim. Mitigation, not enforcement. |
| `tree-check` cannot see gitignored writes | Scope creep into `dist/`, `.next/` is invisible | `--ignored` flag, opt-in because it is noisy |
| Fresh-context review is **not independence** | Same model family, same repo, shared blind spots | Deterministic gates are the real backstop |
| Skills auto-invoke on description match | Vague descriptions misfire; narrow ones never fire | `disable-model-invocation` on anything with side effects |
| Hooks run arbitrary code as you | Third-party plugins are supply chain | First-party only, plus hooks in this repo, plus fixture tests |
| Hooks are not a security boundary | Bypass paths exist by definition | Sandbox for untrusted repos; deny rules for access policy |
| MCP tool output is untrusted text | Prompt injection via tool results | `ask` rules on push / publish / merge |
| Depends on current Claude Code behaviour | Silent drift after updates | `COMPATIBILITY.md` + CI |

---

## A bug this repo found in its own plan

The original security floor used `Read(**/.env*)`. It looked right, validated,
loaded, and showed in `/status` as active.

**It protected nothing outside the working directory.** A single `**/` anchors
at the session's primary working directory; with the session rooted elsewhere,
every project's `.env` and `~/.aws/credentials` stayed readable. `//` anchors at
the filesystem root:

| Pattern | Matches | Misses |
|---|---|---|
| `Read(**/.env)` | any `.env` at or under the **cwd** | parent dirs, **other projects** |
| `Read(//**/.env)` | any `.env` **anywhere** | — |

Caught by testing the rule instead of trusting it. It is now four fixtures —
including `cat` through Bash, which is what decides whether the floor is real
rather than decorative.

That is the argument for the whole repo: **the gates exist because the plan was
wrong, and only a test could tell.**

---

## Install

```bash
git clone <this repo> ~/.claude/skills/harness
```

Loads automatically as `harness@skills-dir` — no marketplace, no install step.
Personal scope has no trust restrictions, so hooks and agents load normally.

```bash
claude plugin validate ~/.claude/skills/harness --strict
claude plugin disable harness@skills-dir   # to turn off
```

`SKILL.md` edits apply immediately; changes to `hooks/` or `agents/` need
`/reload-plugins`.

## Requirements

Python 3 on `PATH` (`python`, `python3`, or `py -3`). Git, for `tree-check`.
