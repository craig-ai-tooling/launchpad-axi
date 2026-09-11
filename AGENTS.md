# AGENTS.md

Primary context file for **every** AI agent working in this repo (Claude Code, Copilot,
Cursor, Codex, or a human). Read this first. Everything else loads on demand.

---

## Why

Agent-ergonomic CLI over the PaletteAI Inference Launchpad admin API: sign in with console credentials, create clients (consumers), mint their lpai_ API tokens, and batch-process a CSV to fill a token per row. Sibling to palette-axi and monday-axi.

---

## What — project map

| Path | What lives here |
|---|---|
| `launchpad_axi/` | Application code |
| `tests/` | Test suites |
| `docs/` | Standards, loaded on demand (see Progressive disclosure) |
| `ralph/` | Autonomous loop: plan, prompt, progress notebook |
| `.specify/` | Spec Kit: constitution, templates, feature specs |
| `.claude/hooks/` | Enforced guardrails (see Enforcement) |
| `.github/workflows/` | CI + issue automation |

---

## How — the only commands that matter

Keep this table honest. A stale command here costs more than a missing one.

| Task | Command |
|---|---|
| Install | `python -m pip install -e ".[dev]"` |
| Build | `python -m compileall launchpad_axi` |
| Test (all) | `python -m unittest discover -s tests` |
| Test (single) | `python -m unittest discover -s tests` |
| Lint | `ruff check .` |
| Format | `ruff check .` |
| Typecheck | `` |

**Definition of done** — a change is not done until build, test, and lint all pass.
CI runs exactly these commands; do not hand-wave them locally.

---

## Three lanes of work

All three inherit the same hooks, the same constitution, the same docs.

**1. Feature — Spec Kit + Ralph.** Anything with more than one moving part.
```
/speckit-constitution → /speckit-specify → /speckit-plan → /speckit-tasks → /speckit-implement
```
Templates must flag unknowns as `NEEDS CLARIFICATION` rather than guessing. If the
spec is ambiguous, stop and ask — do not invent requirements.

**2. Quick fix.** A typo, a one-line bug, a bad copy string. No spec, no ceremony.
Fix it, prove it, then append one line to `docs/fixes-log.md`:
```
- 2026-01-15 — Logout left stale token in localStorage; clear on signOut(). (#42)
```

**3. GitHub issue → automated PR.** Label an issue `claude-fix`. A runner picks it
up, works under these same rules, and opens a PR. It never pushes to `main`.

---

## Progressive disclosure — load only what the task needs

Do not read all of these. Read the one that matches what you are about to change.

| Touching… | Read |
|---|---|
| Credentials, tokens, secret handling, TLS | `docs/security.md` |
| Anything at all | this file |

---

## Conventions

One example each. Match the surrounding code over the example if they conflict.

**Naming** — modules and functions `snake_case`; each CLI subcommand has a handler named `cmd_<verb>`.
```
def cmd_provision(a):  # one handler per subcommand, dispatched by argparse
```

**Errors** — never swallow. Fail loud, with context. `sys.exit("message")` for a
user-facing failure; per-row batch failures are collected and reported, never dropped.
```
if not tok:
    sys.exit("failed: %s" % res)
```

**Tests** — offline; the network layer (`consumers`/`apply_op`/`cid`) is monkeypatched.
A PR that changes batch or column logic adds or updates a `tests/` case.
```
cli.apply_op = fake_apply  # stub the network, assert on the written CSV
```

**Comments** — explain *why*, never *what*. If the code needs a "what" comment,
rewrite the code.

---

## Enforcement — not suggestions

Standards live in `.claude/hooks/` and `.github/workflows/`, not in prose. Prose
gets skimmed; hooks do not.

| Hook | Fires on | Does |
|---|---|---|
| `danger-guard.sh` | `PreToolUse` (Bash) | **Blocks** `rm -rf /`, `rm -rf ~`, force-push to main/master, `git reset --hard origin`, `DROP`/`TRUNCATE TABLE`, `mkfs`, `dd` to a device. Exit 2 with a reason. |
| `format-and-lint.sh` | `PostToolUse` (Write/Edit) | Formats + auto-fixes the changed file. No-ops if the tool is not installed. |
| `session-start.sh` | `SessionStart` | Injects git status, open TODOs, and this checklist. |

Do not disable, bypass, or route around a hook. If a guard is wrong, fix the guard
in a PR — that is a code change with a review, which is the point.

---

## Hard rules

- **Never commit secrets.** No keys, tokens, or `.env` files. Secret scanning is on.
- **Never push to `main`.** Branch, PR, review. The automation follows this too.
- **Never invent a requirement.** Unknown → `NEEDS CLARIFICATION` → ask.
- **Never leave the tree broken.** Build + test + lint green before you commit.
- **Prefer editing over creating.** A new file needs a reason.
- **The token is the credential.** Never log it, never commit it, show it once.
