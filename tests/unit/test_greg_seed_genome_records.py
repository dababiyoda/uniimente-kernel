"""The 2026-10-01 seed-genome directive's records, held to what they claim.

Directive section 2: every material requirement carries 18 fields, intent lifecycle and
implementation maturity are tracked separately, and every crosswalk row of both reviews maps to
a requirement. Section 18: one backcast, P0-P13 reconciled with C1-C8, subordinate to the active
node. Section 19: five roles, exactly two passes, one decision, no fabricated approval. These
tests read the records and the source; they never trust a record about itself.
"""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/intent/sources/GREG-SEED-GENOME-DIRECTIVE-2026-10-01-source.md"
LEDGER = ROOT / "docs/collaboration/requirements-greg-seed-genome-20261001.json"
DELIBERATION = ROOT / "docs/collaboration/deliberation-greg-seed-genome-20261001.json"
UMBRELLA = ROOT / "docs/intent/INTENT-20261001-greg-seed-genome.json"
ADR = ROOT / "docs/decisions/ADR-20261001-greg-seed-genome.md"
FIELDS = ("requirement_id", "exact_source_excerpt", "source_location", "source_date", "intended_effect",
          "interpretation", "canonical_owner", "lifecycle_state", "implementation_state", "authority_scope",
          "dependencies", "implementation_refs", "tests", "evidence_refs", "failure_condition", "next_gate", "owner",
          "review_trigger")
STATES = {"active", "implemented", "deferred", "superseded", "prohibited", "exploratory", "conflicted", "needs_evidence"}


def body():
    text = SOURCE.read_text(encoding="utf-8")
    return text.split("=== BEGIN VERBATIM TEXT ===\n", 1)[1].split("=== END VERBATIM TEXT ===", 1)[0]


def test_the_source_is_verbatim_and_its_digest_holds():
    text = SOURCE.read_text(encoding="utf-8")
    declared = re.search(r"sha256 of that text: `([0-9a-f]{64})`", text).group(1)
    assert hashlib.sha256(body().encode()).hexdigest() == declared
    for quote in ("absolute meniscus", "NOTHING IS DISCONNECTED", "Verified Cross-Geometry Routing Gain"):
        assert quote in body()


def test_every_crosswalk_row_maps_to_a_requirement_with_all_eighteen_fields():
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert tuple(ledger["fields"]) == FIELDS
    rows = {r["requirement_id"]: r for r in ledger["requirements"]}
    codes = re.findall(r"^(A\d\d(?:\.\d)?|B\d\d|BFIRST|BTEST) \|", body(), re.M)
    assert len(codes) == 122 and {f"SG-{c}" for c in codes} <= set(rows)
    for r in rows.values():
        assert set(FIELDS) <= set(r), r["requirement_id"]
        assert r["lifecycle_state"] in STATES and r["implementation_state"] in ledger["implementation_states"]
        assert r["exact_source_excerpt"] in body(), r["requirement_id"]
        for path in r["implementation_refs"] + r["tests"] + r["evidence_refs"]:
            assert (ROOT / path).exists(), (r["requirement_id"], path)
        if r["implementation_state"] == "VERIFIED_IN_TESTED_ENVIRONMENT":
            assert r["tests"] and r["evidence_refs"], r["requirement_id"]


def test_completion_contract_and_known_ambiguities_are_each_a_requirement():
    rows = json.loads(LEDGER.read_text(encoding="utf-8"))["requirements"]
    assert sum(r["requirement_id"].startswith("SG-C") for r in rows) == 11
    assert sum(r["requirement_id"].startswith("SG-K") for r in rows) == 8


def test_deliberation_has_five_roles_two_passes_one_decision_and_no_fabricated_approval():
    d = json.loads(DELIBERATION.read_text(encoding="utf-8"))
    roles = {r["role"].lower() for r in d["roles"]}
    assert {"founder-intent steward", "systems architect", "adversarial reviewer", "operator and maintainer",
            "evidence and welfare guardian"} <= roles
    assert d["decision"] == d["pass_2"]["recommendation"] == "EXPERIMENT"
    assert d["authority_impact"]["approval_status"] != "approved" and d["authority_impact"]["changes_authority"] is False
    ids = {x["id"] for x in d["pass_1"]["disadvantages"]}
    assert ids == {x["disadvantage_id"] for x in d["pass_2"]["pass_1_disadvantage_dispositions"]}
    assert "single agent" in d["roles"][0]["position"].lower() or any("one agent" in r["position"].lower()
                                                                       for r in d["roles"])
    adr = ADR.read_text(encoding="utf-8")
    assert f"`{d['decision']}`" in adr and d["decision_id"] in adr and "Stage-gate" in adr


def test_umbrella_intent_carries_the_ledger_fields():
    u = json.loads(UMBRELLA.read_text(encoding="utf-8"))
    for field in ("intent_id", "statement", "source_refs", "owner", "state", "binding_scope",
                  "constitutional_constraints", "success_evidence", "failure_evidence", "dependencies", "conflicts",
                  "next_review_trigger", "supersedes", "superseded_by", "implementation_refs"):
        assert u.get(field) is not None, field
    assert u["intent_id"] == "INTENT-20261001-greg-seed-genome" and u["state"] in STATES


def test_one_backcast_p0_to_p13_subordinate_to_the_active_node():
    path = json.loads((ROOT / "greg/path.json").read_text(encoding="utf-8"))
    [ws] = [w for w in path["workstreams"] if w["id"] == "cognition_cortex"]
    assert ws["subordinate_to"] == "N1" and ws["metric"] == "Verified Cross-Geometry Routing Gain"
    nodes = {n["id"]: n for n in ws["nodes"]}
    assert list(nodes) == [f"P{k}" for k in range(14)]
    node_ids = {n["id"] for n in path["nodes"]}
    for n in nodes.values():
        for field in ("title", "owner", "dependency", "budget_ceiling", "review_trigger", "falsification",
                      "smallest_next_experiment", "status", "maps_to"):
            assert n.get(field), (n["id"], field)
        assert n["maps_to"] in node_ids
    assert set(ws["reconciles"]) == {f"C{k}" for k in range(1, 9)}
    assert {p for ps in ws["reconciles"].values() for p in ps if p.startswith("P")} <= set(nodes)
    statuses = [n["status"] for n in nodes.values()]
    assert not any(s.startswith("ACTIVE") for s in statuses[4:]), "later nodes are horizons, never activated by listing"
