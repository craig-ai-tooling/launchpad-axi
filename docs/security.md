# Security

> Loaded when: handling user input, authorization, secrets, or routes.
> Referenced by `.specify/memory/constitution.md` as a hard gate.

## Non-negotiables

### 1. Authorization is the launchpad's job, server-side
This tool is a client. It never makes an access decision of its own — the launchpad
authenticates the session token and authorizes every `/admin/*` call. The tool's
only job is to hold that token safely and briefly.

```python
# The session token is cached user-only, never world-readable:
os.chmod(TOKEN_FILE, 0o600)
```

### 2. Sanitize input, encode output
- Validate at the boundary, against a schema. Reject unknown fields.
- Parameterized queries only. String-concatenated SQL is never acceptable.
- Escape on output by context (HTML vs attribute vs URL vs JS).
- Never `innerHTML` / `dangerouslySetInnerHTML` with user data. If unavoidable,
  sanitize with a maintained library and document why.

```python
name = (r.get(ucol) or "").strip()
if not name:                 # reject a blank row rather than mint a nameless client
    errors.append((i, "(blank)", "empty username"))
    continue
```

### 3. Secret hygiene
- Secrets come from the environment or a secret manager. Never a source file.
- `.env` is gitignored; `.env.example` documents the *names* only.
- Never log a secret, token, or full request body containing one.
- Rotate anything that has ever been committed — assume it is public forever.
- GitHub secret scanning + push protection are enabled on this repo.

### 4. Dependencies
- Dependabot is enabled. Security updates get merged promptly, not eventually.
- New dependency requires justification: what does it do that stdlib cannot?

## Transport

All API calls go over HTTPS. The lab launchpad presents a **private-CA** certificate,
so TLS verification is deliberately disabled (`ssl.CERT_NONE`) — scoped to that lab
base URL only, and documented here so it is a known exception, not an accident. Do not
copy that pattern for a public endpoint.

## Pre-merge security checklist

- [ ] No secret added to the repo (CI + push protection verify this)
- [ ] No token, password, or session value written to logs or a committed file
- [ ] Any file that receives a minted token is created with restrictive perms
- [ ] TLS verification is disabled only for the documented lab host, nowhere else
- [ ] No new dependency without justification (stdlib-first)
- [ ] Errors surfaced to the user leak no credentials
