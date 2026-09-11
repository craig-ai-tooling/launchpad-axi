"""Offline unit tests for the batch CSV flow — no network, no live launchpad.

The network-touching functions (consumers/apply_op/cid) are monkeypatched, so
these exercise the column detection, token write-back, and idempotency logic.
Run: python -m unittest discover -s tests
"""
import argparse
import csv
import os
import tempfile
import unittest

from launchpad_axi import cli


def _args(infile, out, **over):
    base = dict(infile=infile, out=out, username_col=None, token_col=None,
                label="test", expires=None, dry_run=False)
    base.update(over)
    return argparse.Namespace(**base)


def _write_csv(path, rows, header=("username", "email", "token")):
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


class FindColTest(unittest.TestCase):
    def test_alias_match(self):
        self.assertEqual(cli.find_col(["User", "Email"], None, ["username", "user"]), "User")

    def test_explicit_flag_wins(self):
        self.assertEqual(cli.find_col(["a", "login"], "login", ["username"]), "login")

    def test_no_match(self):
        self.assertIsNone(cli.find_col(["x", "y"], None, ["username", "user"]))


class BatchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.infile = os.path.join(self.tmp, "in.csv")
        self.outfile = os.path.join(self.tmp, "out.csv")
        # Stub the network layer.
        self._minted = []
        cli.consumers = lambda: []
        cli.cid = lambda name: "usr_" + name

        def fake_apply(fields, confirmed=True):
            if fields["op"] == "create_consumer":
                return {"applied": True}
            if fields["op"] == "create_token":
                tok = "lpai_%s" % fields["consumer"]
                self._minted.append(tok)
                return {"applied": True, "id": "tok_x", "token": tok}
            return {"error": "unexpected op"}

        cli.apply_op = fake_apply

    def test_mints_token_per_row(self):
        _write_csv(self.infile, [["alice", "a@x.test", ""], ["bob", "b@x.test", ""]])
        cli.cmd_batch(_args(self.infile, self.outfile))
        out = _read_csv(self.outfile)
        self.assertEqual(len(out), 2)
        self.assertTrue(all(r["token"].startswith("lpai_") for r in out))
        self.assertEqual(out[0]["email"], "a@x.test")  # original columns preserved
        self.assertEqual(len(self._minted), 2)

    def test_skips_rows_that_already_have_a_token(self):
        _write_csv(self.infile, [["alice", "a@x.test", "lpai_existing"], ["bob", "b@x.test", ""]])
        cli.cmd_batch(_args(self.infile, self.outfile))
        out = _read_csv(self.outfile)
        self.assertEqual(out[0]["token"], "lpai_existing")  # untouched
        self.assertTrue(out[1]["token"].startswith("lpai_"))
        self.assertEqual(len(self._minted), 1)  # only bob

    def test_dry_run_writes_no_tokens(self):
        _write_csv(self.infile, [["alice", "a@x.test", ""]])
        cli.cmd_batch(_args(self.infile, self.outfile, dry_run=True))
        out = _read_csv(self.outfile)
        self.assertEqual(out[0]["token"], "DRY-create")
        self.assertEqual(len(self._minted), 0)

    def test_adds_token_column_when_missing(self):
        _write_csv(self.infile, [["alice", "a@x.test"]], header=("username", "email"))
        cli.cmd_batch(_args(self.infile, self.outfile))
        out = _read_csv(self.outfile)
        self.assertIn("token", out[0])
        self.assertTrue(out[0]["token"].startswith("lpai_"))


if __name__ == "__main__":
    unittest.main()
