"""Reviewer's mutants of the retained-receipt change that the builder's gate does not list.
Runs each against the builder's three test files in a scratch copy; prints which file (if any) fails."""
import os, shutil, subprocess, sys, tempfile, re
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
GATE = "tests/unit/test_greg_retained_receipt.py"
FILES = ([GATE, "tests/unit/test_greg_retained_receipt_history.py",
          "tests/integration/test_greg_retained_receipt_process.py"] if not os.environ.get("NEIGHBOURS_ONLY") else []) + sys.argv[2:]
M = "greg/missions.py"
A = "greg/authority.py"
MUTANTS = [
    ("A1 a recovered receipt of a paid dispatch books no spend", M,
     '                    receipt, cost_usd=float(s.get("cost_usd", 0.0)),\n                    reused="retained receipt of a dispatch',
     '                    receipt, cost_usd=0.0,\n                    reused="retained receipt of a dispatch'),
    ("A2 a recovered receipt is not said to be recovered", M,
     'reused="retained receipt of a dispatch the body did not record before it stopped", **base)', '**base)'),
    ("A3 a compensation the founder declined is asked about again", M,
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED")', 'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED")'),
    ("A4 an uncertain compensation counts as settled (its lost question is never asked)", M,
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED")',
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED", "UNCERTAIN")'),
    ("A5 an unavailable compensation counts as settled (its lost question is never asked)", M,
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED")',
     'COMPENSATION_SETTLED = ("DONE", "FOUNDER_DECIDED", "DECLINED", "UNAVAILABLE")'),
    ("A6 the interrupted-worker rule is applied to every capability", M,
     '        aid = s["action_id"]\n        if (manifest.capability_id == "worker.commission" and outcome.status == "DONE"\n',
     '        aid = s["action_id"]\n        if (True and outcome.status == "DONE"\n'),
    ("A7 a recovered interrupted worker keeps the reuse reason, not the interruption's", M,
     'without a conflict there.)\n            outcome.status = "UNCERTAIN"\n            outcome.reasons = ["worker execution interrupted; partial outcome and spend require reconciliation"]\n',
     'without a conflict there.)\n            outcome.status = "UNCERTAIN"\n'),
    ("A8 the dispatch site's own copy of the interrupted-worker rule is removed (builder: redundant)", M,
     'signed_scopes=signed)\n        if (manifest.capability_id == "worker.commission" and outcome.status == "DONE"\n',
     'signed_scopes=signed)\n        if (False and outcome.status == "DONE"\n'),
    ("A9 a lost question about a record with no reasons names no failure", M,
     'failure=closed[aid].get("reasons") or [closed[aid].get("status")])', 'failure=closed[aid].get("reasons"))'),
    ("A10 only a REFUSED compensation's lost question is asked", M,
     '                if closed[aid].get("status") not in COMPENSATION_SETTLED:\n',
     '                if closed[aid].get("status") == "REFUSED":\n'),
    ("A11 a fresh dispatch is read by the old two-way reading (not by outcome_of)", A,
     '            return self.outcome_of(self.ledger.find(record.receipt_hash), cost_usd=cost_usd, **base)',
     '            _r = self.ledger.find(record.receipt_hash)\n'
     '            _res = _r.payload["result"]\n'
     '            if _res.get("result_class") != "positive":\n'
     '                return ActionOutcome("REFUSED", [_res.get("observed_outcome", "capability failed")],\n'
     '                                     receipt_hash=_r.hash, grant_id=grant["grant_id"],\n'
     '                                     failure_class=_res.get("failure_class"), **base)\n'
     '            return ActionOutcome("DONE", [], output=_res.get("output"), receipt_hash=_r.hash,\n'
     '                                 grant_id=grant["grant_id"], cost_usd=cost_usd,\n'
     '                                 output_artifact=_res.get("output_artifact"), **base)'),
    ("A12 a retained receipt under the earlier scope form reports the new proposal, not the one it was dispatched as", A,
     'reused="retained legacy receipt; no redispatch",\n                                       **old_base)',
     'reused="retained legacy receipt; no redispatch",\n                                       **base)'),
    ("A13 an unreadable retained receipt in act's reuse branch is not reported at all (falls to a fresh dispatch refusal)", A,
     '            return self.outcome_of(receipt, cost_usd=cost_usd, reused="retained receipt reused after restart", **base)',
     '            _o = self.outcome_of(receipt, cost_usd=cost_usd, reused="retained receipt reused after restart", **base)\n'
     '            if _o.status != "UNCERTAIN":\n                return _o\n'
     '            return ActionOutcome("REFUSED", _o.reasons, receipt_hash=_o.receipt_hash, grant_id=_o.grant_id, **base)'),
    ("A14 a legacy unreadable receipt is treated as a refusal", A,
     '                return self.outcome_of(old_receipt, cost_usd=cost_usd, reused="retained legacy receipt; no redispatch",\n                                       **old_base)',
     '                _o = self.outcome_of(old_receipt, cost_usd=cost_usd, reused="retained legacy receipt; no redispatch",\n                                       **old_base)\n'
     '                if _o.status == "UNCERTAIN":\n                    _o.status = "REFUSED"\n                return _o'),
    ("B1 the engine's recovery reads an unreadable receipt as a refusal (the office still says unknown)", M,
     '                    reused="retained receipt of a dispatch the body did not record before it stopped", **base)\n',
     '                    reused="retained receipt of a dispatch the body did not record before it stopped", **base)\n'
     '                if outcome.status == "UNCERTAIN":\n                    outcome.status = "REFUSED"\n'),
    ("B2 a compensation that completed is asked about as if it had not", M,
     '                if closed[aid].get("status") not in COMPENSATION_SETTLED:\n', '                if True:\n'),
]

def main():
    only = os.environ.get("ONLY")
    with tempfile.TemporaryDirectory(prefix="adv-negrc-mut-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        for name, target, old, new in MUTANTS:
            if only and name.split()[0] not in only.split(","):
                continue
            path = repo / target
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", original.count(old), name, flush=True); continue
            path.write_text(original.replace(old, new))
            for top in ("greg", "tests"):
                for c in (repo / top).rglob("__pycache__"):
                    shutil.rmtree(c, ignore_errors=True)
            try:
                r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rf", *FILES],
                                   cwd=repo, env=env, capture_output=True, text=True, timeout=1200)
            finally:
                path.write_text(original)
            failed = re.findall(r"^FAILED (\S+?)::(\S+)", r.stdout, flags=re.M)
            by = {}
            for f, t in failed:
                by.setdefault(f, []).append(t)
            tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-300:]
            verdict = ("CAUGHT_BY_GATE_FILE" if GATE in by else "CAUGHT_ONLY_OUTSIDE_GATE_FILE" if by else "SURVIVED")
            print(verdict, "|", name, "|", {f.split('/')[-1]: len(v) for f, v in by.items()}, "|", tail, flush=True)
            for f, v in by.items():
                for t in v[:4]:
                    print("      ", f.split('/')[-1], t, flush=True)

main()
