"""Each mutant removes one safeguard added by the review fixes (S1-S10); the resolution unit tests must catch it."""
import subprocess, sys
from pathlib import Path
ROOT = Path(sys.argv[1]); F = ROOT / "greg/cognition/settlement.py"
ORIG = F.read_text()
MUTANTS = {
 "N1 S1 signed body not compared": ('\n                or not _signed_body_matches(data, command["body"], ("receipt", "resolves", "accept"))):', '):'),
 "N2 S1 one signed command reused": ('command is None or data["command_digest"] in seen', 'command is None'),
 "N3 S2 any resolution adjudicates": ('held_by_acceptance = any(e.event_id in accepted for e in live)', 'held_by_acceptance = applied is not None'),
 "N4 S2 partial invalidation accepted": ('        if standing:\n            raise', '        if False:\n            raise'),
 "N5 S3 dedupe against rejected facts": ('live = [e for e in existing if ruling.get(e.event_id, True)]', 'live = existing'),
 "N6 S3 one fact per receipt and value": ('key = receipt if not existing else [receipt, "fact", source, repr(realized), len(existing)]', 'key = receipt if not existing else [receipt, "fact", repr(realized)]'),
 "N7 S4 journal order wins": ('key=lambda item: (item[0], item[1])', 'key=lambda item: item[1]'),
 "N8 S5 succeeded only when prior is None": ('        if outcome.get("answer_version") and _base_identity(outcome) in legacy:', '        if prior is None and outcome.get("answer_version") and _base_identity(outcome) in legacy:'),
 "N9 S6 failed check hidden by dispute": ('        if not outcome["correct"]:        # the signed check failed', '        if False:'),
 "N10 S7 unsettleable dispute weighed": ('        if row["mission_id"] not in settling:', '        if False:'),
 "N11 S8 Laplace flips ignored": ('            if min(laplace) < other_mean < max(laplace):', '            if False:'),
 "N12 S9 unsigned fact eligible (replay)": ('(accept in named and accept in signed_facts', '(accept in named'),
 "N13 S9 unsigned fact eligible (row)": ('"eligible_to_accept": e.event_id in signed_facts\n                and', '"eligible_to_accept": True\n                and'),
 "N14 S10 engine label hashed": ('if k not in ANSWER_PROVENANCE_FIELDS}', 'if True}'),
}
TESTS = ["tests/unit/test_greg_outcome_resolution.py", "tests/unit/test_greg_pending_construction_realization.py",
         "tests/unit/test_greg_outcome_resolution_signed.py"]
rows = []
try:
    for name, (old, new) in MUTANTS.items():
        assert ORIG.count(old) == 1, (name, ORIG.count(old))
        F.write_text(ORIG.replace(old, new))
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
                           cwd=ROOT, capture_output=True, text=True)
        failing = [l.split("::")[-1].split(" ")[0] for l in r.stdout.splitlines() if l.startswith("FAILED")]
        rows.append(f"{'CAUGHT ' if r.returncode else 'MISSED '} {name}: {failing[:1]}")
        print(rows[-1], flush=True)
finally:
    F.write_text(ORIG)
print(f"{sum(r.startswith('CAUGHT') for r in rows)} of {len(rows)} caught")
