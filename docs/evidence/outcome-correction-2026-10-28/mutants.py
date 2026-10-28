"""Each mutant removes one safeguard of the evidence-repair change; a fast unit set must catch it."""
import subprocess, sys
from pathlib import Path
ROOT = Path(sys.argv[1]); F = ROOT / "greg/cognition/settlement.py"
ORIG = F.read_text()
MUTANTS = {
 "M1 answer_version dropped from claim identity": ('    if outcome.get("answer_version") is not None:\n        fields["answer_version"]', '    if False:\n        fields["answer_version"]'),
 "M2 resolutions need no accepted founder command": ('            if e.payload.get("kind") == "resolution" and e.payload.get("command_digest") in signed]', '            if e.payload.get("kind") == "resolution"]'),
 "M3 settlement accepts a non-independent observation": ('                                        and by_id[accept].payload.get("source") in INDEPENDENT_SOURCES))):\n            applied = event', '                                        ))):\n            applied = event'),
 "M4 the latest resolution revives facts it does not name": ('            ruling.update({fact: fact == accept for fact in named})', '            ruling = {fact: fact == accept for fact in named}'),
 "M5 verdict-concordant values treated as disputed": ('"verdict_concordant" if len(verdicts) == 1 else "disputed"', '"disputed"'),
 "M6 corroboration from another source dropped": ('        if first.payload.get("source") == source:\n            return first.payload', '        if True:\n            return first.payload'),
 "M7 record time accepts a founder report": ('        if facts[accept].payload.get("source") not in INDEPENDENT_SOURCES:', '        if False:'),
 "M8 a partial resolution is accepted": ('        if unnamed:\n            raise', '        if False:\n            raise'),
}
TESTS = ["tests/unit/test_greg_outcome_resolution.py", "tests/unit/test_greg_pending_construction_realization.py",
         "tests/unit/test_greg_construction_realization.py"]
rows = []
try:
    for name, (old, new) in MUTANTS.items():
        assert ORIG.count(old) == 1, name
        F.write_text(ORIG.replace(old, new))
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS],
                           cwd=ROOT, capture_output=True, text=True)
        caught = r.returncode != 0
        failing = [l.split("::")[-1].split(" ")[0] for l in r.stdout.splitlines() if l.startswith("FAILED")]
        rows.append(f"{'CAUGHT ' if caught else 'MISSED '} {name}: {failing[:1]}")
        print(rows[-1], flush=True)
finally:
    F.write_text(ORIG)
print(f"{sum(r.startswith('CAUGHT') for r in rows)} of {len(rows)} caught")
