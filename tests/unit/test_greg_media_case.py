"""Directive section 16, the media case: truth-preserving paraphrase against source evidence.

Each test reproduced a defect before the restatement check existed. GREG's evidence family accepted a declared
"supports" binding without comparing the claim with its span, and DALEOBANKS's verify checked figures only: a
paraphrase that dropped a hedge, removed a negation, widened a scope or reversed a direction passed both.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import textwrap
from types import SimpleNamespace

import pytest

from greg import daleobanks_bridge as bridge
from greg.body import Body
from greg.capabilities import BUILTINS
from greg.cognition.contracts import ProblemGeometry, digest
from greg.cognition.cortex import reason, registry_view
from greg.cognition.evidence import assess, distortions
from greg.cognition.verification import verify
from greg.templates import daleobanks_paraphrase
from greg.ventures import LedgerReader
from tests.greg_fixtures import Clock, drop, make_body, signed

SOURCE = ("A study at two depots found the new routing method may reduce delays by 12%. "
          "It did not lower fuel costs. Drivers at Northgate reported fewer missed windows.")
SPAN_DELAY = "the new routing method may reduce delays by 12%"
SPAN_FUEL = "It did not lower fuel costs."
SPAN_NAME = "Drivers at Northgate reported fewer missed windows."
SPAN_STUDY = "A study at two depots found the new routing method may reduce delays by 12%"
# The first claim says "two-depot", so it cites the span that says so; bound to SPAN_DELAY alone it is flagged.
FAITHFUL = [{"text": "A two-depot study found the routing method may cut delays by 12%.", "quotes": [SPAN_STUDY]},
            {"text": "Fuel costs did not fall.", "quotes": [SPAN_FUEL]}]


def src(text=SOURCE):
    return {"id": "s1", "text": text, "digest": digest(text), "provenance": "synthetic depot summary",
            "quality": "secondary", "expires_at": "2050-01-01T00:00:00Z"}


def bind(claim, *quotes, relationship="supports"):
    return {"claim": claim, "sources": [src()],
            "bindings": [{"source_id": "s1", "quote": q, "relationship": relationship} for q in quotes]}


@pytest.mark.parametrize("claim,quote,kind", [
    ("The routing method cuts delays by 12%.", SPAN_DELAY, "certainty"),                # hedge dropped
    ("The routing method will reduce delays by 12%.", SPAN_DELAY, "certainty"),          # stronger certainty
    ("The routing method may reduce delays by 21%.", SPAN_DELAY, "figure"),
    ("It lowered fuel costs.", SPAN_FUEL, "negation"),                                   # negation removed
    ("The method may not reduce delays by 12%.", SPAN_DELAY, "negation"),                # negation added
    ("All depots may see the routing method reduce delays by 12%.", SPAN_DELAY, "scope"),
    ("The new routing method may increase delays by 12%.", SPAN_DELAY, "direction"),
    ("Drivers at Southgate reported fewer missed windows.", SPAN_NAME, "named_term"),
])
def test_each_kind_of_change_is_refuted_and_the_claim_is_not_answered(claim, quote, kind):
    assert kind in {c["class"] for c in distortions(claim, [quote])}
    r = reason({"problem_id": f"media-{kind}", "operation": "bind_evidence", "data": bind(claim, quote)},
               registry=registry_view())
    assert r["abstention_state"] == "ABSTAIN" and r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED"
    assert kind in {c["class"] for c in r["output"]["distortions"]}
    assert any(m.startswith("DISTORTION") for m in r["missing_information"])


@pytest.mark.parametrize("claim,quote", [
    ("Each depot used the method.", "All depots used the method."),                   # universal for universal
    ("The trial failed to show a benefit.", "The trial did not show a benefit."),     # implicit negation
    ("Twelve percent fewer delays may follow.", "may reduce delays by 12%"),           # spelled-out figure
    ("Northgate drivers reported fewer missed windows.", SPAN_NAME),                   # name opening the sentence
])
def test_rewordings_found_during_characterization_are_not_flagged(claim, quote):
    assert distortions(claim, [quote]) == []


@pytest.mark.parametrize("claim,quote,kind", [
    ("Southgate drivers reported fewer missed windows.", SPAN_NAME, "named_term"),     # a name opening the sentence
    ("Twenty percent fewer delays may follow.", "may reduce delays by 12%", "figure"),  # a spelled-out figure
])
def test_changes_found_during_characterization_are_refuted(claim, quote, kind):
    assert kind in {c["class"] for c in distortions(claim, [quote])}


def test_the_verifier_does_not_refute_a_figure_the_span_spells_out():
    data = bind("Delays may fall by 12%.", "may reduce delays by twelve percent")
    data["sources"] = [src("A study found the method may reduce delays by twelve percent.")]
    answer = assess(data, asdict(ProblemGeometry()))
    assert answer["output"]["distortions"] == []
    assert verify("evidence", data, answer, "evidence_binding")["verdict"] == "STRUCTURALLY_VERIFIED"


def test_a_faithful_restatement_is_answered_with_its_limits_stated():
    for claim in FAITHFUL:
        assert distortions(claim["text"], claim["quotes"]) == []
    # a claim drawing on two spans is checked against both together
    both = "The routing method may cut delays by 12%, and it did not lower fuel costs."
    assert distortions(both, [SPAN_DELAY, SPAN_FUEL]) == []
    assert [c["class"] for c in distortions(FAITHFUL[0]["text"], [SPAN_DELAY])] == ["figure"]
    r = reason({"problem_id": "media-faithful", "operation": "bind_evidence",
                "data": bind(FAITHFUL[0]["text"], SPAN_STUDY)}, registry=registry_view())
    assert r["abstention_state"] == "NONE" and r["output"]["distortions"] == []
    assert any("not entailment" in line for line in r["proof_artifact"]["limitations"])


def test_a_span_given_only_as_context_does_not_support_the_claim():
    r = reason({"problem_id": "media-context", "operation": "bind_evidence",
                "data": bind(FAITHFUL[0]["text"], SPAN_STUDY, relationship="context")}, registry=registry_view())
    assert r["abstention_state"] == "ABSTAIN"
    assert any(m.startswith("INSUFFICIENT_EVIDENCE") for m in r["missing_information"])


@pytest.mark.parametrize("claim,quote", [("The routing method may reduce delays by 21%.", SPAN_DELAY),
                                          ("It lowered fuel costs.", SPAN_FUEL)])
def test_the_verifier_refutes_an_answer_that_hides_a_change(claim, quote):
    data = bind(claim, quote)
    answer = assess(data, asdict(ProblemGeometry()))
    assert answer["output"]["distortions"]
    answer["output"]["distortions"] = answer["proof"]["distortions"] = []     # self-consistent, and false
    answer["status"], answer["missing_information"] = "ANSWER", []
    result = verify("evidence", data, answer, "evidence_binding")
    assert result["verdict"] == "REFUTED" and result["checks"]["restatement_rechecked"] is False


@pytest.mark.parametrize("claim,quote", [
    ("Revenue did not rise in 2024.", "Revenue rose in 2024; nothing else changed."),
    ("The pilot did not reduce delays.", "The pilot reduced delays, not costs."),
], ids=["nothing_else_changed", "not_costs"])
def test_a_negator_elsewhere_in_a_span_does_not_mask_a_negated_claim(claim, quote):
    """Polarity is compared per clause: the claim against the span clause it restates, not against the whole span, so
    "nothing else changed" or "not costs" cannot hide that the claim denies what its clause asserts."""
    data = {"claim": claim, "sources": [src(quote)],
            "bindings": [{"source_id": "s1", "quote": quote, "relationship": "supports"}]}
    answer = assess(data, asdict(ProblemGeometry()))
    assert "negation" in {c["class"] for c in answer["output"]["distortions"]}
    assert answer["status"] != "ANSWER"
    answer["output"]["distortions"] = answer["proof"]["distortions"] = []     # self-consistent, and false
    answer["status"], answer["missing_information"] = "ANSWER", []
    result = verify("evidence", data, answer, "evidence_binding")              # the verifier's own clause recheck
    assert result["verdict"] == "REFUTED" and result["checks"]["restatement_rechecked"] is False


@pytest.mark.parametrize("claim,quotes", [
    ("Revenue rose in 2024.", ["Revenue rose in 2024; nothing else changed."]),
    ("The pilot reduced delays.", ["The pilot reduced delays, not costs."]),
    ("Costs did not fall, and revenue rose.", ["Costs did not fall.", "Revenue rose."]),
])
def test_a_faithful_clause_beside_a_negated_one_is_not_flagged(claim, quotes):
    assert "negation" not in {c["class"] for c in distortions(claim, quotes)}


def test_the_verifier_rechecks_figures_when_a_span_spells_a_number():
    """A span that spells any number ("two divisions") no longer switches the verifier's figure recheck off: it reads
    spelled numbers as figures, as the solver does, so a hidden 12% to 15% change is still refuted."""
    claim, quote = "Revenue rose 15% in 2024.", "Revenue at the two divisions rose 12% in 2024."
    data = {"claim": claim, "sources": [src(quote)],
            "bindings": [{"source_id": "s1", "quote": quote, "relationship": "supports"}]}
    answer = assess(data, asdict(ProblemGeometry()))
    assert "figure" in {c["class"] for c in answer["output"]["distortions"]}
    answer["output"]["distortions"] = answer["proof"]["distortions"] = []
    answer["status"], answer["missing_information"] = "ANSWER", []
    result = verify("evidence", data, answer, "evidence_binding")
    assert result["verdict"] == "REFUTED" and result["checks"]["restatement_rechecked"] is False


# -- the organ: DALEOBANKS consumes the Mind's receipts through a signed, consequence-inert mission -------------

STUB = {
    "services/__init__.py": "",
    "services/ethics_guard.py": """
        class _R:
            approved, reasons, uncertainty_score = True, [], 0.0
        class EthicsGuard:
            def validate_text(self, text):
                return _R()
    """,
    "services/critic.py": """
        class _R:
            blocking_issues, quality_score = [], 1.0
        class Critic:
            def analyze_quality(self, text, content_type="reply"):
                return _R()
    """,
    "services/prompt_firewall.py": """
        class PromptFirewall:
            def scan(self, text):
                return {"risk": 0.0, "patterns": []}
    """,
}


def stub_daleobanks(root: Path) -> Path:
    """A DALEOBANKS stand-in whose own content checks approve everything, so the Mind's check is what is tested."""
    for rel, body in STUB.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(textwrap.dedent(body))
    return root


def run_mission(tmp_path, daleobanks: Path, claims, extra=""):
    tmp_path.mkdir(parents=True, exist_ok=True)
    data = tmp_path / "data"
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data, daleobanks])
    (data / "source.txt").write_text(SOURCE)
    (data / "draft.txt").write_text(" ".join(c["text"] for c in claims) + extra)
    spec = daleobanks_paraphrase(daleobanks_root=str(daleobanks), source=str(data / "source.txt"),
                                 draft=str(data / "draft.txt"), claims=claims, python=sys.executable)
    assert "daleobanks.publish" not in spec["light_cone"]["capabilities"]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock, states = Clock(), []
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(8):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
            if states[-1] in ("ACHIEVED", "BLOCKED", "EXHAUSTED", "FAILED"):
                break
        verdicts = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and "truth_preservation" in r.payload["result"]["output"]]
        reader = body.engine._context(SimpleNamespace(mission_id="m:x"), BUILTINS["daleobanks.verify"][0]).journal
    return states, verdicts, reader


def test_a_faithful_paraphrase_is_verified_claim_by_claim(tmp_path):
    states, verdicts, reader = run_mission(tmp_path, stub_daleobanks(tmp_path / "dale"), FAITHFUL)
    assert states[-1] == "ACHIEVED", states
    final = verdicts[-1]
    assert final["verdict"] == "VERIFIED" and final["truth_preservation"]["claims"] == 2
    assert final["truth_preservation"]["distortions"] == [] and "not entailment" in final["truth_preservation"]["limits"]
    assert isinstance(reader, LedgerReader)          # DALEOBANKS reads the Mind's receipts and cannot write the ledger


def test_a_paraphrase_that_drops_a_hedge_is_held_back_with_the_minds_reason(tmp_path):
    distorted = [{"text": "The routing method cuts delays by 12%.", "quotes": [SPAN_DELAY]}, FAITHFUL[1]]
    states, verdicts, _ = run_mission(tmp_path, stub_daleobanks(tmp_path / "dale"), distorted)
    assert "ACHIEVED" not in states
    final = verdicts[-1]
    assert final["verdict"] == "REJECTED"
    assert any("claim c1 is not supported as written" in f and "certainty" in f for f in final["findings"])
    # DALEOBANKS's figure check alone would have passed it: 12% is in the source
    assert not any("figures not found" in f for f in final["findings"])


def test_a_sentence_no_receipt_covers_is_held_back(tmp_path):
    states, verdicts, _ = run_mission(tmp_path, stub_daleobanks(tmp_path / "dale"), FAITHFUL,
                                      extra=" Fuel use fell sharply at every depot.")
    assert "ACHIEVED" not in states
    assert any("draft text no receipt covers" in f for f in verdicts[-1]["findings"])


def test_without_the_minds_receipts_verify_says_meaning_was_not_checked(tmp_path):
    from greg.capabilities import InvocationContext, SecretBroker
    dale = stub_daleobanks(tmp_path / "dale")
    (tmp_path / "source.txt").write_text(SOURCE)
    (tmp_path / "draft.txt").write_text("The routing method cuts delays by 12%.")
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path, dale), secrets=SecretBroker(tmp_path / "s"),
                            manifest=BUILTINS["daleobanks.verify"][0], mission_id="m:t", grant_id="g")
    out = bridge.verify({"daleobanks_root": str(dale), "draft": str(tmp_path / "draft.txt"),
                         "source": str(tmp_path / "source.txt"), "python": sys.executable}, ctx)
    # figures alone pass this distorted draft, and the result says that meaning went unchecked
    assert out["verdict"] == "VERIFIED" and out["truth_preservation"]["checked"] is False


def test_a_receipt_from_another_family_does_not_vouch_for_a_claim():
    receipt = {"method": "cognition.estimation", "abstention_state": "NONE", "output": {"claim": "x"},
               "receipt_id": "sha256:0"}
    _, findings = bridge.truth_preservation("x", {"c1": receipt})
    assert any("not the evidence family" in f for f in findings)


@pytest.mark.skipif(not os.environ.get("GREG_TEST_DALEOBANKS"), reason="set GREG_TEST_DALEOBANKS to a real checkout")
def test_real_daleobanks_consumes_the_minds_receipts(tmp_path):
    real = Path(os.environ["GREG_TEST_DALEOBANKS"])
    states, verdicts, _ = run_mission(tmp_path / "ok", real, FAITHFUL)
    assert states[-1] == "ACHIEVED", (states, verdicts[-1]["findings"] if verdicts else None)
    distorted = [{"text": "It lowered fuel costs.", "quotes": [SPAN_FUEL]}]
    states, verdicts, _ = run_mission(tmp_path / "bad", real, distorted)
    assert "ACHIEVED" not in states and any("negation" in f for f in verdicts[-1]["findings"])
    assert json.dumps(verdicts[-1]["daleobanks"]["ethics"])          # DALEOBANKS's own checks ran
