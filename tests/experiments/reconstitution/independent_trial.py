"""Score the already frozen experiment against a separately authored case."""
import hashlib
import json
from pathlib import Path

from experiment import Local, Rule, first, run, trace


HERE = Path(__file__).resolve().parent
FIXTURE_DIGEST = "c3e1c97f71a3b0a26307ea9ca59c1a2f1d4ece624181a33f490b4e6b1efe7096"


def main():
    fixture = (HERE / "independent-fixture.json").read_bytes()
    if hashlib.sha256(fixture).hexdigest() != FIXTURE_DIGEST:
        raise ValueError("Independent fixture differs from its original digest")
    spec = json.loads(fixture)
    sources = spec["sources"]
    rules = tuple(Rule(name, role, tuple(needs), provides) for name, role, needs, provides in spec["rules"])
    alive = {rule.name for rule in rules}
    capsule = run()["capsule"]
    outcome = {}
    for label, preference in (("cold", ()), ("inherited", capsule)):
        lab = Local(rules, sources, preference)
        seen = trace(lab, sources, alive)
        expected = spec["expected_terminal_sources"]
        grades = {
            claim: any(
                lab.rules[name].provides == claim and proof.sources == set(support)
                for name, proof in lab.memory.items()
            )
            for claim, support in expected.items()
        }
        outcome[label] = {
            "correct_terminal_support": grades,
            "first_target_round": {target: first(seen, target) for target in spec["targets"]},
            "rule_checks": lab.checks,
            "rewires": lab.rewires,
            "binding_changes": lab.name_changes,
        }
    print(json.dumps({
        "fixture_sha256": FIXTURE_DIGEST,
        "implementation_commit": "c24d671785b5879ea609ebd7b2ef726cc55ea2c2",
        "outcome": outcome,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
