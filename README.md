# launchpad-axi

Agent-ergonomic CLI over the **PaletteAI Inference Launchpad** admin API. Sign in with
console credentials, create clients (consumers), mint their `lpai_` API tokens, and
batch-process a CSV to fill in a token per row. Sibling to `palette-axi` / `monday-axi`.

## Install

```sh
python -m pip install -e ".[dev]"     # or: pipx install .
```

Python 3.10+, standard library only at runtime (no third-party deps).

## Configure

| Env | Default | Meaning |
|---|---|---|
| `LP_BASE` | `https://launchpad.lab.internal` | Launchpad base URL — **set this to your host** |
| `LP_USER` | `admin` | Console username |
| `LP_PASS` | — | Console password (prompted if unset) |
| `LP_TOKEN_FILE` | `~/.launchpad_admin_token` | Where the session token is cached |

The lab presents a private-CA certificate; TLS verification is intentionally disabled
for that host.

## Use

```sh
export LP_PASS='…'
launchpad-axi login                      # ~12h session token, cached

launchpad-axi add-client acme-prod       # create a client (consumer)
launchpad-axi mint acme-prod ci-key      # mint its token — plaintext printed ONCE
launchpad-axi provision acme-prod ci-key # add-client + mint in one step

launchpad-axi list                       # clients + tokens
launchpad-axi revoke tok_9ec941d3        # revoke a token by id
launchpad-axi retire acme-prod           # soft-delete a client (state -> retired)
```

Any write can be previewed with `--dry-run`, which returns the launchpad's own
simulation (blast radius, risk tier) without mutating anything.

### Batch: a token per CSV row

Give it a CSV with a `username` column (and a blank `token` column); it creates a
client and mints a token for each row, writing the token back:

```sh
launchpad-axi batch clients.csv                 # -> clients.tokens.csv
launchpad-axi batch clients.csv -o out.csv --dry-run
```

Input (`examples/clients-example.csv`):

```csv
username,email,token
team-alpha,team-alpha@example.com,
team-bravo,team-bravo@example.com,
```

Output — same columns, `token` filled:

```csv
username,email,token
team-alpha,team-alpha@example.com,lpai_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
team-bravo,team-bravo@example.com,lpai_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Behaviour worth knowing:

- **The username is the only thing stored on a client.** A launchpad client has a
  single writable field (`display_name`). A second column such as `email` is carried
  through to the output untouched but is **not** recorded anywhere in the launchpad.
- **The output CSV is the only copy of the tokens.** Plaintext is shown once at mint;
  the API returns only a prefix afterwards. Treat the output file as a secret bundle —
  if it leaks, revoke and re-mint.
- **Re-runnable.** A row that already has a non-empty token is skipped, so re-running
  on a partly-processed file (or after adding rows) never double-mints or duplicates a
  client. Per-row failures don't abort the batch — the token is left blank and the row
  is reported on stderr.
- `--label` tags the minted tokens (default `csv-import`) so a batch is easy to find
  and revoke later; `--expires <RFC3339>` sets an expiry.

## Develop

```sh
python -m unittest discover -s tests     # tests (offline; network is stubbed)
ruff check .                             # lint
python -m compileall launchpad_axi       # compile check
```

See [AGENTS.md](AGENTS.md) for the full contract.
