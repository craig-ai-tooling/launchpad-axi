"""The contract `doctor` exists to enforce: an unreachable launchpad or a
missing/rejected session token must never render as healthy. On a runner
where nothing is configured, doctor must refuse (exit 1), not exit 0.

These tests are offline except for the two subprocess cases, which point
LP_BASE at an unroutable host and LP_TOKEN_FILE at a path that does not
exist — no live launchpad required.
"""
import argparse
import contextlib
import csv
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from launchpad_axi import cli

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(args, **envkw):
    env = dict(os.environ)
    env.update(envkw)
    return subprocess.run([sys.executable, "-m", "launchpad_axi", *args],
                          capture_output=True, text=True, cwd=ROOT, env=env, timeout=60)


class TestConnectorTable(unittest.TestCase):
    def test_every_connector_declares_a_valid_need_and_a_callable_probe(self):
        for name, need, why, probe in cli.CONNECTORS:
            self.assertIn(need, ("required", "optional"), name)
            self.assertTrue(why, name)
            self.assertTrue(callable(probe), name)

    def test_both_connectors_are_required(self):
        need = {c[0]: c[1] for c in cli.CONNECTORS}
        self.assertEqual(need, {"launchpad-api": "required", "session-token": "required"})

    def test_only_the_two_documented_connectors_exist(self):
        self.assertEqual(sorted(c[0] for c in cli.CONNECTORS), ["launchpad-api", "session-token"])


class TestProbeIsolation(unittest.TestCase):
    def test_a_probe_that_raises_is_rendered_not_propagated(self):
        """doctor's whole job is probing; a probe blowing up must not take it down."""
        def boom():
            raise RuntimeError("kaboom")

        saved = cli.CONNECTORS[:]
        cli.CONNECTORS[:] = [("explodes", "required", "test probe", boom)]
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                with self.assertRaises(SystemExit) as ctx:
                    cli.cmd_doctor(argparse.Namespace(json=True))
            self.assertEqual(ctx.exception.code, 1)
            data = json.loads(buf.getvalue())
            self.assertIn("explodes", data["required_down"])
            row = data["connectors"][0]
            self.assertEqual(row["status"], "down")
            self.assertIn("RuntimeError", row["detail"])
            self.assertIn("kaboom", row["detail"])
        finally:
            cli.CONNECTORS[:] = saved


class TestDoctorExitCodes(unittest.TestCase):
    def test_doctor_refuses_when_nothing_is_configured(self):
        with tempfile.TemporaryDirectory() as d:
            missing_token = os.path.join(d, "nope", "tok")
            r = run(["doctor", "--json"], LP_TOKEN_FILE=missing_token, LP_BASE="https://127.0.0.1:9")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            data = json.loads(r.stdout)
            self.assertTrue(data["required_down"])
            self.assertIn("launchpad-api", data["required_down"])
            self.assertIn("session-token", data["required_down"])

    def test_doctor_json_is_parseable_and_has_the_documented_keys(self):
        with tempfile.TemporaryDirectory() as d:
            missing_token = os.path.join(d, "nope", "tok")
            r = run(["doctor", "--json"], LP_TOKEN_FILE=missing_token, LP_BASE="https://127.0.0.1:9")
            data = json.loads(r.stdout)
            for k in ("version", "connectors", "config", "required_down"):
                self.assertIn(k, data)

    def test_lp_pass_never_appears_as_its_value_in_json(self):
        with tempfile.TemporaryDirectory() as d:
            missing_token = os.path.join(d, "nope", "tok")
            r = run(["doctor", "--json"], LP_TOKEN_FILE=missing_token, LP_BASE="https://127.0.0.1:9",
                    LP_PASS="super-secret-value")
            self.assertNotIn("super-secret-value", r.stdout)
            data = json.loads(r.stdout)
            lp_pass = next(c for c in data["config"] if c["var"] == "LP_PASS")
            self.assertEqual(lp_pass["value"], "set")


class TestTextTableEncoding(unittest.TestCase):
    """`doctor`'s plain-text table now renders through the shared `toon()`
    (launchpad_axi/axi.py, vendored from craig-ai-tooling/axi-py) instead of
    the tool's own `_toon`. The old encoder only ever quoted the `detail`
    column, so a comma or quote in any other column broke the row. These pin
    the fixed behaviour: every column is quoted when it needs it, and an
    empty table renders as a definitive `(none)` rather than a bare header
    that reads the same as a truncated one."""

    def test_a_comma_in_a_non_detail_column_is_quoted(self):
        def has_a_comma():
            return "down, retrying", "transient", "launchpad-axi login"

        saved = cli.CONNECTORS[:]
        cli.CONNECTORS[:] = [("launchpad-api", "required", "test probe", has_a_comma)]
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                with self.assertRaises(SystemExit):
                    cli.cmd_doctor(argparse.Namespace(json=False))
            out = buf.getvalue()
            self.assertIn('"down, retrying"', out)
            # the row still parses to exactly 4 cells: the quoted status
            # column's own comma does not split it in two.
            row = [ln for ln in out.splitlines() if ln.startswith("  launchpad-api,")][0]
            cells = next(csv.reader([row.strip()]))
            self.assertEqual(cells, ["launchpad-api", "required", "down, retrying",
                                     "transient | fix: launchpad-axi login"])
        finally:
            cli.CONNECTORS[:] = saved

    def test_toon_renders_an_empty_table_as_a_definitive_none(self):
        self.assertEqual(cli.toon("connectors", ["name", "need", "status", "detail"], []),
                         "connectors[0]{name,need,status,detail}: (none)")


if __name__ == "__main__":
    unittest.main()
