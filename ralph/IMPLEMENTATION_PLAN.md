# Implementation Plan

> Populated from Spec Kit `/speckit-tasks` output, then worked top-to-bottom by
> `ralph/loop.sh` — one task per iteration.

## How to fill this in

1. `/speckit-specify` → `/speckit-plan` → `/speckit-tasks`
2. Paste the generated tasks below, highest priority first.
3. Each task must be **independently completable and verifiable in one iteration**.
   If a task cannot be finished and tested on its own, split it.

Good task: `Add idle-timeout to session store; unit test covers expiry at 30m`
Bad task:  `Implement authentication`

## Conventions

- `- [ ]` open · `- [x]` done · `- [!]` blocked (reason in `PROGRESS.md`)
- Keep priority order meaningful — the loop always takes the topmost open item.

---

## Tasks

<!-- Replace this block with real tasks. -->

- [ ] Add `--json` output to `mint` and `provision` so callers capture token + id programmatically.
- [ ] Add a `rotate <client>` command: mint a fresh token, then revoke that client's previous ones.
- [ ] Teach `batch` to set a client's tier on create from an optional `--tier` flag or CSV column.

---

## Out of scope

Things deliberately NOT being done, so no iteration wanders into them.

- Managing console *users* (`create_user`) — this tool manages clients (consumers) and their tokens only.
