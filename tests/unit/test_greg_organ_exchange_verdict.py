"""The mission-path organ exchange states the verdict the founder-facing memo would, never the engine's uncapped one.

Measured 2026-10-30 at the CI job-8 organ pins (DALEOBANKS 664ac98c, WealthMachine 0e80582d): on the seed below,
WealthMachine answers "go" and organ.exchange's receipt said "go", while organs.exchange (the memo path) caps the same
answer to needs_more_evidence because the packet leaves governing_bottleneck unevidenced. Two governed
implementations of Bridge A disagreed on what the founder may be told.
"""
from greg import organs
from greg.organ_exchange import binding_verdict
from greg.ventures import VERDICT_RANK
from tests.unit.test_greg_organs import SEED, ctx, journal, live_organs, organ_roots  # noqa: F401 (fixture)

PACKET = {"id": "p-1", "schema_version": "1.1", "created_at": "2026-10-30T00:00:00Z",
          "observed_pain": "renters cannot prove repairs were requested", "audience": "renters",
          "buyer_type": "tenant unions", "smallest_validation_action": "ask five unions", "evidence": ["a claim"]}
CASES = [{"case": name, "argument": "a", "stance": "for", "severity": "low"} for name in ("bull", "bear", "do_nothing")]
ASSESSMENT = {"id": "a-1", "schema_version": "1.1", "created_at": "2026-10-30T00:00:00Z",
              "opportunity_packet_id": "p-1", "go_no_go": "go", "requires_human_approval": True, "cases": CASES}


def test_an_engine_go_on_a_packet_with_unevidenced_canonical_fields_is_capped():
    verdict, why = organs._binding(PACKET, ASSESSMENT)
    assert verdict == "needs_more_evidence" and "governing_bottleneck" in why and "cap the engine's 'go'" in why


def test_the_cap_never_raises_a_lower_verdict():
    assert organs._binding(PACKET, {**ASSESSMENT, "go_no_go": "kill"})[0] == "kill"


def test_the_mission_path_applies_the_memo_paths_rule_exactly():
    for go in ("go", "needs_more_evidence", "kill"):
        assessment = {**ASSESSMENT, "go_no_go": go}
        expected = binding_verdict(go, ["governing_bottleneck"], PACKET["evidence"])
        assert organs._binding(PACKET, assessment) == expected


def test_messages_the_kernel_cannot_read_leave_nothing_evidenced():
    unreadable_packet = {k: v for k, v in PACKET.items() if k != "observed_pain"}     # fails the wire contract
    no_committee = {**ASSESSMENT, "cases": []}                                          # the adapter refuses it
    for packet, assessment in ((unreadable_packet, ASSESSMENT), (PACKET, no_committee)):
        verdict, why = organs._binding(packet, assessment)
        assert verdict == "needs_more_evidence" and "could not read the wire messages" in why


def test_live_exchange_states_the_capped_verdict_beside_the_engines(tmp_path, journal):  # noqa: F811
    params = live_organs()
    out = organs.exchange({**params, "seed": SEED}, ctx(tmp_path, journal, roots=organ_roots(params)))
    assert out["engine_verdict"] == out["assessment"]["go_no_go"]          # the engine's answer is still kept
    assert VERDICT_RANK[out["verdict"]] <= VERDICT_RANK[out["engine_verdict"]]
    # DALEOBANKS's wire packet carries nothing the adapter maps to governing_bottleneck, so no binding "go" exists
    assert out["verdict"] != "go" and "governing_bottleneck" in out["verdict_why"]
