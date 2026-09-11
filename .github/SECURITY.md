# Security Policy

## Reporting a vulnerability

Do **not** open a public issue for a security problem.

Use GitHub private vulnerability reporting:
**Security → Advisories → Report a vulnerability**.

Expect an acknowledgement within 3 business days.

## What is enabled on this repository

| Control | Status |
|---|---|
| Secret scanning | On — automatic and free for public repos |
| Push protection | Enable in Settings → Code security |
| Dependabot alerts + updates | On (`.github/dependabot.yml`) |
| Dependency review on PRs | Off — the action needs GitHub Advanced Security, unavailable on a free private repo |
| CodeQL code scanning | Needs GHAS on a private repo; `codeql.yml` is dormant (manual dispatch only) |
| Branch protection | Configure a ruleset on `main` (see `docs/github-automation.md`) |

## Secrets

Never commit a secret. If one is committed, assume it is public permanently:
rotate it immediately, then remove it from history.

Application-level security rules live in [`docs/security.md`](docs/security.md).
