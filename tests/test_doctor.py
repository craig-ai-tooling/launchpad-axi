"""The contract `doctor` exists to enforce: an unreachable launchpad or a
missing/rejected session token must never render as healthy. On a runner
where nothing is configured, doctor must refuse (exit 1), not exit 0.

These tests are offline except for the two subprocess cases, which point
LP_BASE at an unroutable host and LP_TOKEN_FILE at a path that does not
exist — no live launchpad required.
"""
import argparse
import contextlib
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


if __name__ == "__main__":
    unittest.main()
