#!/usr/bin/env python3
"""launchpad-axi — add clients & mint API tokens on the PaletteAI Inference Launchpad.

Auth model : admin console creds -> POST /admin/login -> bearer session token (~12h).
Write model: POST /admin/apply {"proposed_op":{...op..., "confirmed":true}}
             (confirmed:false returns a dry-run simulation: blast radius, risk tier.)

Env:
  LP_BASE        default https://launchpad.lab.internal (set this to your host)
  LP_USER        default admin
  LP_PASS        password (else prompt)
  LP_TOKEN_FILE  where the session token is cached (default ~/.launchpad_admin_token)
"""
import argparse
import csv
import getpass
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

from launchpad_axi import __version__
from launchpad_axi.axi import toon

BASE = os.environ.get("LP_BASE", "https://launchpad.lab.internal").rstrip("/")
TOKEN_FILE = os.environ.get("LP_TOKEN_FILE", os.path.expanduser("~/.launchpad_admin_token"))

# The lab presents a private-CA cert; verification is intentionally disabled for it.
_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def _req(method, path, body=None, token=None):
    """Make one JSON request. Returns (status_code, parsed_body)."""
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, context=_CTX, timeout=15) as resp:  # noqa: S310 (fixed base)
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {"error": "http %d" % e.code}


def _token():
    try:
        t = open(TOKEN_FILE).read().strip()
        if t:
            return t
    except FileNotFoundError:
        pass
    sys.exit("no session token — run: launchpad-axi login")


def apply_op(fields, confirmed=True):
    """POST one operation to /admin/apply. Returns the parsed response body."""
    op = dict(fields)
    op["confirmed"] = confirmed
    _st, body = _req("POST", "/admin/apply", {"proposed_op": op}, token=_token())
    return body


def consumers():
    return _req("GET", "/admin/consumers", token=_token())[1].get("consumers", [])


def cid(name):
    """Resolve an active consumer id by display_name, or None."""
    for c in consumers():
        if c["display_name"] == name and c["state"] != "retired":
            return c["id"]
    return None


def cmd_login(a):
    user = os.environ.get("LP_USER", "admin")
    pw = os.environ.get("LP_PASS") or getpass.getpass("password: ")
    st, b = _req("POST", "/admin/login", {"username": user, "password": pw})
    if st != 200 or "token" not in b:
        sys.exit("login failed: %s" % b)
    with open(TOKEN_FILE, "w") as fh:
        fh.write(b["token"])
    os.chmod(TOKEN_FILE, 0o600)
    print("ok  role=%s  expires=%s" % (b.get("role"), b.get("expires_at")))


def cmd_add(a):
    if cid(a.name):
        print("exists:", cid(a.name))
        return
    r = apply_op({"op": "create_consumer", "display_name": a.name}, confirmed=not a.dry_run)
    if a.dry_run:
        print(json.dumps(r, indent=2))
        return
    if r.get("applied"):
        print("created:", cid(a.name), "(%s)" % a.name)
    else:
        sys.exit("failed: %s" % r)


def cmd_mint(a):
    cid_ = cid(a.name)
    if not cid_:
        sys.exit("no such client: %s" % a.name)
    f = {"op": "create_token", "consumer": cid_, "label": a.label}
    if a.expires:
        f["expires_at"] = a.expires
    r = apply_op(f, confirmed=not a.dry_run)
    if a.dry_run:
        print(json.dumps(r, indent=2))
        return
    tok = r.get("token")
    if not tok:
        sys.exit("failed: %s" % r)
    print(tok)  # plaintext — shown once, store it now


def cmd_provision(a):
    cmd_add(argparse.Namespace(name=a.name, dry_run=False))
    cmd_mint(argparse.Namespace(name=a.name, label=a.label, expires=a.expires, dry_run=False))


def cmd_list(a):
    print("# clients")
    for c in consumers():
        print(" ", c["id"], c["display_name"], c["state"], c.get("tier", ""))
    print("# tokens")
    for t in _req("GET", "/admin/tokens", token=_token())[1].get("tokens", []):
        print(" ", t["id"], t["label"], "revoked=%s" % t["revoked"], t["consumer"])


def cmd_revoke(a):
    print(apply_op({"op": "revoke_token", "id": a.token_id}))


def cmd_retire(a):
    c = cid(a.name)
    if not c:
        sys.exit("no active client: %s" % a.name)
    print(apply_op({"op": "delete_consumer", "consumer": c}))


def cmd_whoami(a):
    print(json.dumps(_req("GET", "/admin/whoami", token=_token())[1]))


# ── doctor ───────────────────────────────────────────────────────────────
# The whole contract in one table: (name, need, why, probe). `need` is what
# decides what a failure means. Both connectors here are required — this tool
# cannot do anything without a reachable launchpad and a valid session token.
# A probe must never raise; cmd_doctor also wraps every call so one broken
# probe can't take the whole command down — probing is its entire job.

def _probe_launchpad_api():
    """is LP_BASE reachable? A connection failure, DNS failure or TLS error is
    down with the reason. Any HTTP response (even a 404) means the host
    answered, so that counts as reachable. Short timeout so doctor never hangs."""
    try:
        req = urllib.request.Request(BASE + "/", method="GET")
        try:
            urllib.request.urlopen(req, context=_CTX, timeout=10)
        except urllib.error.HTTPError:
            pass  # the server answered — that is reachability, regardless of status
        return "ok", "%s reachable" % BASE, ""
    except Exception as e:
        detail = "%s unreachable: %s: %s" % (BASE, type(e).__name__, e)
        return "down", detail[:120], "check LP_BASE and network/DNS/TLS"


def _probe_session_token():
    """does the token file exist and is it readable; if so, validate it with
    GET /admin/whoami. A missing file, an unreadable file, or a rejected
    token are all down with fix: launchpad-axi login."""
    if not os.path.exists(TOKEN_FILE):
        return "down", "no token file at %s" % TOKEN_FILE, "launchpad-axi login"
    try:
        tok = open(TOKEN_FILE).read().strip()
    except OSError as e:
        return "down", ("token file unreadable: %s" % e)[:120], "launchpad-axi login"
    if not tok:
        return "down", "token file at %s is empty" % TOKEN_FILE, "launchpad-axi login"
    try:
        st, _body = _req("GET", "/admin/whoami", token=tok)
    except Exception as e:
        detail = "whoami check failed: %s: %s" % (type(e).__name__, e)
        return "down", detail[:120], "launchpad-axi login"
    if st != 200:
        return "down", "token rejected (HTTP %d)" % st, "launchpad-axi login"
    return "ok", "session token valid (whoami HTTP 200)", ""


CONNECTORS = [
    ("launchpad-api", "required", "every command talks to LP_BASE", _probe_launchpad_api),
    ("session-token", "required", "every admin call needs a valid session token", _probe_session_token),
]


def _src(name):
    return "env" if os.environ.get(name) else "default"


def cmd_doctor(a):
    """What is configured, what is not, and exactly what fixes each gap.
    Exits 0 only when every required connector is ok; exits 1 if one is down.
    Never prints a secret: LP_PASS renders as the literal word set/unset, and
    no token value, prefix, or length is ever shown — --json included."""
    rows, results = [], []
    for name, need, why, probe in CONNECTORS:
        try:
            status, detail, fix = probe()
        except Exception as e:  # a probe blowing up must not take doctor down
            status, detail, fix = "down", ("probe raised %s: %s" % (type(e).__name__, e))[:120], ""
        results.append({"name": name, "need": need, "why": why, "status": status,
                        "detail": detail, "fix": fix})
        rows.append({"name": name, "need": need, "status": status,
                     "detail": detail + (" | fix: %s" % fix if fix else "")})

    cfg = [
        {"var": "LP_BASE", "value": BASE, "source": _src("LP_BASE")},
        {"var": "LP_USER", "value": os.environ.get("LP_USER", "admin"), "source": _src("LP_USER")},
        {"var": "LP_PASS", "value": "set" if os.environ.get("LP_PASS") else "unset",
         "source": _src("LP_PASS")},
        {"var": "LP_TOKEN_FILE", "value": TOKEN_FILE, "source": _src("LP_TOKEN_FILE")},
    ]

    bad = [r for r in results if r["need"] == "required" and r["status"] != "ok"]

    if getattr(a, "json", False):
        print(json.dumps({
            "version": __version__,
            "connectors": results,
            "config": cfg,
            "required_down": [r["name"] for r in bad],
        }, indent=2))
        sys.exit(1 if bad else 0)

    print(toon("connectors", ["name", "need", "status", "detail"], rows))
    print(toon("config", ["var", "value", "source"], cfg))
    sys.exit(1 if bad else 0)


def find_col(fieldnames, wanted, aliases):
    """Pick a CSV column: an explicit --flag wins, else the first matching alias."""
    lut = {c.lower().strip(): c for c in fieldnames}
    if wanted and wanted.lower() in lut:
        return lut[wanted.lower()]
    for alias in aliases:
        if alias in lut:
            return lut[alias]
    return None


def cmd_batch(a):
    with open(a.infile, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        sys.exit("empty CSV: %s" % a.infile)
    fields = list(rows[0].keys())
    ucol = find_col(fields, a.username_col, ["username", "user", "name", "client", "display_name"])
    if not ucol:
        sys.exit("no username column found (have: %s) — pass --username-col" % ", ".join(fields))
    tcol = find_col(fields, a.token_col, ["token", "api_token", "apikey", "api_key"]) or "token"
    out_fields = fields + ([tcol] if tcol not in fields else [])

    # Pre-index existing active consumers so re-runs don't create duplicates.
    existing = {c["display_name"]: c["id"] for c in consumers() if c["state"] != "retired"}
    made, minted, skipped, errors = [], 0, 0, []

    for i, r in enumerate(rows, 1):
        name = (r.get(ucol) or "").strip()
        if not name:
            errors.append((i, "(blank)", "empty username"))
            continue
        if r.get(tcol, "").strip():  # idempotent: row already has a token
            skipped += 1
            continue
        try:
            if a.dry_run:
                r[tcol] = "DRY-%s" % ("reuse" if name in existing else "create")
                continue
            cid_ = existing.get(name)
            if not cid_:
                if not apply_op({"op": "create_consumer", "display_name": name}).get("applied"):
                    raise RuntimeError("create_consumer failed")
                cid_ = cid(name)
                existing[name] = cid_
                made.append(name)
            f = {"op": "create_token", "consumer": cid_, "label": a.label}
            if a.expires:
                f["expires_at"] = a.expires
            res = apply_op(f)
            tok = res.get("token")
            if not tok:
                raise RuntimeError("mint failed: %s" % res)
            r[tcol] = tok
            minted += 1
        except Exception as e:  # keep going; record the row and move on
            errors.append((i, name, str(e)))
            r[tcol] = ""

    outpath = a.out or (a.infile.rsplit(".", 1)[0] + ".tokens.csv")
    with open(outpath, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_fields)
        w.writeheader()
        w.writerows(rows)
    print("wrote %s" % outpath, file=sys.stderr)
    print("  clients created : %d" % len(made), file=sys.stderr)
    print("  tokens minted   : %d" % minted, file=sys.stderr)
    print("  rows skipped    : %d (already had a token)" % skipped, file=sys.stderr)
    print("  errors          : %d" % len(errors), file=sys.stderr)
    for i, n, m in errors:
        print("    row %d (%s): %s" % (i, n, m), file=sys.stderr)
    if a.dry_run:
        print("  [DRY-RUN] no writes performed", file=sys.stderr)


def build_parser():
    p = argparse.ArgumentParser(prog="launchpad-axi", description="PaletteAI Launchpad admin CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="exchange console creds for a session token").set_defaults(f=cmd_login)
    sub.add_parser("whoami", help="show the current session identity").set_defaults(f=cmd_whoami)
    sub.add_parser("list", help="list clients and tokens").set_defaults(f=cmd_list)

    x = sub.add_parser("doctor", help="check whether the launchpad API and session token are usable")
    x.add_argument("--json", action="store_true", help="emit JSON instead of the text tables")
    x.set_defaults(f=cmd_doctor)

    x = sub.add_parser("add-client", help="create a client (consumer)")
    x.add_argument("name")
    x.add_argument("--dry-run", action="store_true")
    x.set_defaults(f=cmd_add)

    x = sub.add_parser("mint", help="mint an API token for a client")
    x.add_argument("name")
    x.add_argument("label", nargs="?", default="key")
    x.add_argument("--expires", help="RFC3339 expiry, e.g. 2026-12-31T00:00:00Z")
    x.add_argument("--dry-run", action="store_true")
    x.set_defaults(f=cmd_mint)

    x = sub.add_parser("provision", help="add-client + mint in one step")
    x.add_argument("name")
    x.add_argument("label", nargs="?", default="key")
    x.add_argument("--expires")
    x.set_defaults(f=cmd_provision)

    x = sub.add_parser("revoke", help="revoke a token by id")
    x.add_argument("token_id")
    x.set_defaults(f=cmd_revoke)

    x = sub.add_parser("retire", help="soft-delete a client by name")
    x.add_argument("name")
    x.set_defaults(f=cmd_retire)

    x = sub.add_parser("batch", help="CSV in -> CSV out with a token per row")
    x.add_argument("infile")
    x.add_argument("-o", "--out")
    x.add_argument("--username-col")
    x.add_argument("--token-col")
    x.add_argument("--label", default="csv-import")
    x.add_argument("--expires")
    x.add_argument("--dry-run", action="store_true")
    x.set_defaults(f=cmd_batch)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.f(args)


if __name__ == "__main__":
    main()
