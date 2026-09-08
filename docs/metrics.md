# Harness Baseline — Phase 1 (measured, not assumed)

Captured **2026-09-08** on Claude Code **2.1.263**, win32-x64, PowerShell primary. Moves into `docs/metrics.md` at Phase 2.

## Environment

| | |
|---|---|
| Claude Code | 2.1.263 (native, commit 37ae3f38d765) |
| Model | Opus 5 — **1M context window** |
| Binary | `C:\Users\tooya\.local\bin\claude.exe` |
| Account | Pro/Max — no managed settings, no org policy |
| `claude doctor` | No installation issues found |

## Row 1 — before / after Phase 1

| Metric | Before (virgin) | After 1b |
|---|---|---|
| System prompt | 4.7k (0.5%) | 4.7k |
| System tools (loaded) | 27.1k (2.7%) | 27.1k |
| System tools (deferred) | 16.5k | 16.5k |
| **MCP tools (loaded)** | **0 tokens / 55 tools** | **0 tokens** |
| MCP tools (if all loaded) | 32.9k | 32.9k |
| **Skills listing** | **2.9k (0.3%) / 18 skills** | 2.9k → grows in Phase 2 |
| Marketplace plugins | 0 | **1** (`skill-creator`) |
| Deny rules | **0** | **6, verified working** |
| Ask rules | 0 | 3 |
| Hooks | 0 | 0 (Phase 3) |
| LSP | 0 | **0 — deliberately none** |

*(Messages/conversation excluded — it's session-specific noise, not harness overhead.)*

## The three numbers that matter

### 1. Skill listing budget — real headroom, correctly computed

`skillListingBudgetFraction` defaults to **1% of the model's context window**. On a 1M-window Opus 5 that is **~10k tokens**, not the ~2k I assumed from a 200k window.

| | |
|---|---|
| Budget (1% of 1M) | ~10,000 tokens |
| Currently used | **2,900 tokens (18 skills)** — 29% of budget |
| Average per skill | **~161 tokens** |
| Harness adds (6–7 skills) | ~1,100 tokens → ~39% of budget |
| **ECC's 286 skills** | **~46,000 tokens → 460% of budget** |

**The ECC argument survives the correction and gets sharper:** 4.6× over budget guarantees description dropping, and that's a *conservative* estimate — descriptions cap at 1,536 chars (~384 tokens), so a catalog with fuller descriptions than these built-ins runs higher.

**Worth verifying later:** the budget is a fraction of *the model's* window, so the same 2.9k of built-in skills would be ~145% of a 200k-window model's 2k budget. If true, truncation is already happening on smaller-window models with no user skills installed at all. Test before claiming it.

### 2. MCP deferral — confirmed on this machine

```
MCP tools · /mcp (loaded on-demand)
└ 55 tools · 0 tokens
```

**55 tools, zero tokens.** This is the direct empirical proof of the v2 correction. Full schemas would be **32.9k**, of which **Gmail alone is ~22k across 29 tools** (`search_threads` 2.5k, `create_label` 2k, `send_message` 1.8k, `update_label` 1.8k, `update_draft` 1.7k…).

So the pre-Tool-Search framing — "every connected server's schemas are re-sent every turn" — would have cost 32.9k/turn here. It costs 0. Any harness advice built on the old model is optimizing a cost that no longer exists.

### 3. Skill usage data exists — the eviction rule is directly supported

`/plugin` → **Stats** tab gives exactly what the plan's monthly eviction needs:

```
skill      source        context  7d tokens   uses  last used
humanizer  userSettings     ~100          -     1×  10 days
```

Per-skill listing cost, 7-day attributed tokens, use count, last used. `All loaded skills have been used at least once.`

## Tooling corrections from this measurement

| Plan said | Actual |
|---|---|
| `/skill-doctor` | **Moved.** Skill usage and context costs are now the **Stats tab in `/plugin`**. |
| "`/skills` isn't a command" | **Wrong — it exists.** `/context` points at it directly. My correction of the reviewer was the error. |
| Budget ~2k (200k window) | **~10k** (1% of 1M) |
| MCP schemas cost per turn | **0 when deferred**; 32.9k only if all loaded |

## Config state

`~/.claude/settings.json` — 6 deny rules, 3 ask rules, `skill-creator` enabled. Deny rules survived the plugin install's rewrite of the file.

## FINDING — the plan's deny rules were wrong, caught by testing them

The approved plan specified `Read(**/.env*)`. **It blocked nothing outside the working directory.** A nested `apps/web/.env.local` fixture read cleanly with the rule active, valid, and loaded.

Cause — a single `**/` anchors at the session's **primary working directory**:

| Pattern | Matches | Does NOT match |
|---|---|---|
| `Read(.env)` / `Read(**/.env)` | any `.env` at or under the **current directory** | parent directories, **other projects** |
| `Read(//**/.env)` | any `.env` **anywhere on the filesystem** | — |

Windows paths normalize to POSIX (`C:\Users\x` → `/c/Users/x`), so `//**/.env*` spans all drives; `//c/**/.env*` covers one.

**Impact:** with the session rooted at `C:\Windows\System32`, every project's `.env` and `~/.aws/credentials` stayed readable — while `/status` showed an active security floor. Worse than no rule, because it invites you to stop worrying.

### Verification after fix

| Test | Before fix | After fix |
|---|---|---|
| Read root `.env` | read | ✔ denied |
| Read nested `apps/web/.env.local` | **read** | ✔ denied |
| Read `apps/web/server.key` | read | ✔ denied |
| **`cat` nested `.env.local` via Bash** | — | ✔ **denied** |

The Bash row decides whether the floor is real: deny rules cover shell reads, not just file tools. Without it, one `cat` defeats the whole layer.

**Phase 3:** these four become `tests/fixtures/` cases so a regression to the single-`**` form fails CI.

## Decisions taken

- **No LSP installed.** Stack answer was "nothing specific yet" — installing `typescript-lsp` + `pyright-lsp` now would be exactly the context tax the plan warns about. Install when a real project starts.
- **`context7` deferred** to first real project, same reasoning. Cheap (deferred = 0 tokens) but another moving part with nothing to ground yet.
- **`skill-creator` installed** — earns its place now because Phase 2 is skill authoring.
- **Both TS and Python stack templates** written in Phase 2, since work will span both.
