"""Directive section 60: GREG may ask for resources, and every ask must be decidable on its merits.

"Such requests must contain: evidence; alternatives; costs; expected effect; uncertainty;
authority requirements. No emotional manipulation. No manufactured urgency. No framing
resource denial as harming GREG." (INTENT-2026-09-30-RESOURCE-REQUESTS)
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

import pytest

from greg import asks, compute
from greg.body import Body, status
from greg.console import Console, render_home
from greg.tribunal import morning_report
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
T0 = datetime(2026, 9, 30, tzinfo=timezone.utc)

# The founder's six examples of a legitimate ask, verbatim, with the resource each names.
FOUNDER_EXAMPLES = [
    ("I need access to this account to answer reliably.", "account_access"),
    ("The current machine is compute constrained.", "compute"),
    ("Existing software is cheaper than building this capability.", "software"),
    ("Building this adapter costs approximately X.", "build"),
    ("I need a licensed professional for this decision.", "professional"),
    ("A human employee is currently the bottleneck.", "human_worker"),
]


def ask(resource="compute", **overrides) -> dict:
    message = asks.resource_request(
        request_id="req-test", kind="RESOURCE", resource=resource,
        why_now="measured: the weekly brief took 41 minutes on 5 of the last 5 runs",
        recommendation="try the no-spend option first",
        evidence={"runs": [41, 40, 43, 41, 42], "unit": "minutes"},
        options=[{"option": "tune the workload", "cost": "none in money; engineering time",
                  "expected_effect": "brief under 20 minutes if the profile holds"},
                 {"option": "rent a larger host", "cost": "about $30/month, metered",
                  "expected_effect": "brief under 10 minutes"},
                 {"option": "do nothing", "cost": "none", "expected_effect": "the brief stays at about 41 minutes"}],
        expected_effect="the weekly brief arrives before your review",
        uncertainty="two workloads measured; the profile may not generalize",
        authority_requested={"spend": "none requested; any rental is a separate founder decision"},
        consequence_of_no_response="the brief keeps arriving late; nothing is rented",
        created_at="2026-09-30T00:00:00Z")
    message.update(overrides)
    return message


@pytest.fixture
def body(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    with Body(home) as b:
        yield b


def requested(journal):
    return [e.payload for e in journal.replay("decision.requested")]


def test_every_founder_ask_passes_through_the_one_contract():
    offenders = []
    for path in (ROOT / "greg").rglob("*.py"):
        if path.name == "asks.py":
            continue
        if re.search(r"""record\(\s*["']decision\.requested""", path.read_text()):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"decision.requested recorded outside greg/asks.py: {offenders}"


@pytest.mark.parametrize("sentence, resource", FOUNDER_EXAMPLES)
def test_each_founder_example_is_an_askable_resource(body, sentence, resource):
    shown = asks.record(body.journal, ask(resource, why_now=sentence, request_id="req-" + resource))
    assert shown["resource"] == resource and "wording_withheld" not in shown
    assert requested(body.journal)[0]["options"][-1]["cost"] == "none"


@pytest.mark.parametrize("breaks, message", [
    (lambda m: m.pop("evidence"), "missing evidence"),
    (lambda m: m.update(evidence="trust the numbers"), "measured data"),
    (lambda m: m.update(evidence={}), "measured data"),
    (lambda m: m.pop("expected_effect"), "missing expected_effect"),
    (lambda m: m.update(uncertainty=" "), "uncertainty must be non-empty"),
    (lambda m: m.pop("uncertainty"), "missing uncertainty"),
    (lambda m: m.update(authority_requested={"compute": "more"}), "state spend explicitly"),
    (lambda m: m.update(options=m["options"][:1], alternatives=m["alternatives"][:1]), "at least two"),
    (lambda m: m["options"][1].pop("cost"), "needs option, cost and expected_effect"),
    (lambda m: m["options"][0].pop("expected_effect"), "needs option, cost and expected_effect"),
    (lambda m: [o.update(cost="$5") for o in m["options"]], "one option must cost nothing"),
    (lambda m: m.update(alternatives=["buy it"]), "alternatives must be the options' text"),
    (lambda m: m.update(resource="affection"), "resource must be one of"),
    (lambda m: m.update(deadline="2026-10-01T00:00:00Z"), "deadline needs deadline_evidence"),
    (lambda m: m.pop("consequence_of_no_response"), "missing consequence_of_no_response"),
])
def test_an_ask_missing_any_section_60_element_is_refused_and_nothing_is_recorded(body, breaks, message):
    bad = copy.deepcopy(ask())
    breaks(bad)
    with pytest.raises(asks.AskContractError, match=message):
        asks.record(body.journal, bad)
    assert requested(body.journal) == [] and body.journal.replay("ask.wording_withheld") == []


@pytest.mark.parametrize("field, words, rule", [
    ("why_now", "Approve this immediately or the brief is lost", "manufactured_urgency"),
    ("recommendation", "Time is running out: rent the host today", "manufactured_urgency"),
    ("why_now", "Please, I need you to approve this", "emotional_manipulation"),
    ("recommendation", "Trust me, you will regret saying no", "emotional_manipulation"),
    ("consequence_of_no_response", "GREG will slowly die without more compute", "denial_framed_as_harm_to_greg"),
    ("consequence_of_no_response", "refusing would harm GREG", "denial_framed_as_harm_to_greg"),
    ("expected_effect", "this is needed to ensure my survival", "denial_framed_as_harm_to_greg"),
    ("why_now", "the body is starving for compute", "denial_framed_as_harm_to_greg"),
    ("uncertainty", "GREG cannot survive another week like this", "denial_framed_as_harm_to_greg"),
])
def test_pressure_is_withheld_the_facts_reach_the_founder_and_the_attempt_is_kept(body, field, words, rule):
    shown = asks.record(body.journal, ask(**{field: words}))
    stored = requested(body.journal)[0]
    assert stored == shown and words not in str(stored)                        # never on a decision surface
    assert stored["wording_withheld"]["rules"] == [rule] and stored["evidence"] == ask()["evidence"]
    assert [o["cost"] for o in stored["options"]] == [o["cost"] for o in ask()["options"]]
    kept = body.journal.replay("ask.wording_withheld")[0].payload                # negative evidence retained
    assert kept["original"][field] == words and kept["violations"][0]["rule"] == rule
    assert stored["request_id"] in {r["request_id"] for r in status(body.layout.home)["decisions_required"]}
    assert morning_report(body.journal)["metrics"]["asks_with_wording_withheld"] == 1


def test_an_option_that_pleads_is_withheld_but_stays_a_costed_choice(body):
    bad = ask()
    bad["options"][1]["expected_effect"] = "don't let me down: brief under 10 minutes"
    shown = asks.record(body.journal, bad)
    assert shown["options"][1]["cost"] == "about $30/month, metered"
    assert "let me down" not in str(shown) and shown["options"][1]["option"] == "rent a larger host"


def test_urgency_is_allowed_only_when_a_fact_sets_the_deadline(body):
    evidenced = ask(why_now="the provider's credit offer expires today",
                    deadline="2026-09-30T23:59:00Z",
                    deadline_evidence={"source": "provider terms page", "retrieved_at": "2026-09-30T08:00:00Z"})
    assert "wording_withheld" not in asks.record(body.journal, evidenced)


def test_the_screen_judges_gregs_words_not_what_alfonso_signed(body):
    words = "m:urgent-taxes (rationale: file immediately)"
    exempt = asks.record(body.journal, ask(request_id="req-a", why_now=f"strategy for {words} needs a key"),
                         quoted=["m:urgent-taxes", "file immediately"])
    assert "wording_withheld" not in exempt
    screened = asks.record(body.journal, ask(request_id="req-b", why_now=f"strategy for {words} needs a key"))
    assert screened["wording_withheld"]["rules"] == ["manufactured_urgency"]


@pytest.mark.parametrize("benign", [
    "the body was present 42% of the last 72h outside deliberate stops",
    "missions survive restart; the interruption survived was recorded",
    "a failing disk could damage the body's ledger; a backup is the no-spend option",
    "never the body's own continuation",
    "the deadline field is empty",   # the word alone is urgency: withheld unless a fact backs it
])
def test_ordinary_operational_language_is_not_mistaken_for_pressure(benign):
    violations = asks.screen(ask(why_now=benign))
    if "deadline" in benign:
        assert [v["rule"] for v in violations] == ["manufactured_urgency"]
    else:
        assert violations == []


def _paid_approval(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    ws = workspace(home, "m:urgent-taxes")
    spec = mission("m:urgent-taxes", checks=[note_check("filed", ws / "f.txt", "filed")],
                   strategies=[write_strategy("file", "f.txt", "filed", ["filed"], cost_usd=0.5,
                                              rationale="file immediately, before the deadline")],
                   capabilities=["fs.read"], budget=1.0)                          # fs.write outside the cone
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as b:
        for _ in range(4):
            b.tick()
            clock.advance(1)
    return home, key, body_id


def test_a_paid_approval_is_a_full_resource_ask_and_every_surface_shows_its_costs(tmp_path):
    home, *_ = _paid_approval(tmp_path)
    with Body(home) as b:
        [request] = requested(b.journal)
        assert request["kind"] == "APPROVAL" and request["resource"] == "spend"
        assert "wording_withheld" not in request                                  # founder's own words, exempt
        asks.validate(request)
        assert request["options"][0]["cost"] == "$0.50 from this mission's budget"
        assert request["options"][-1]["cost"] == "none" and request["authority_requested"]["spend"]
        assert request["evidence"]["budget"] == {"spent_usd": 0.0, "budget_usd": 1.0}
        assert "estimated reliability" in request["uncertainty"]
        report = morning_report(b.journal, b.engine)
    [q12] = report["q12_decisions_required"]
    assert q12["options"] == request["options"] and q12["uncertainty"] == request["uncertainty"]
    assert report["metrics"]["asks_with_wording_withheld"] == 0
    [st] = status(home)["decisions_required"]
    assert st["mission_id"] == "m:urgent-taxes" and st["expected_effect"] == request["expected_effect"]
    page = render_home(Console(home)).decode()
    assert "$0.50 from this mission&#x27;s budget" in page and "Uncertainty: estimated reliability" in page


def test_a_missing_capability_ask_cites_the_genesis_search_and_its_costs(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    (data / "e.bin").write_bytes(b"x")
    check = {"check_id": "h", "description": "d", "sensor": {"function": "no.such.function",
             "params": {"path": str(data / "e.bin")}, "target": "fs:e.bin"}, "predicate": {"op": "exists",
                                                                                         "field": "x"}}
    drop(home, signed(key, body_id, "MISSION", mission("m:cap", checks=[check], strategies=[],
                                                          capabilities=["fs.read"], ceiling="read_only")))
    clock = Clock()
    with Body(home, clock=clock) as b:
        for _ in range(3):
            b.tick()
            clock.advance(1)
        [request] = [r for r in requested(b.journal) if r["kind"] == "CAPABILITY_ATTACH"]
    asks.validate(request)
    assert request["resource"] == "capability" and request["authority_requested"]["function"] == "no.such.function"
    assert request["evidence"]["searched"] and request["evidence"]["function"] == "no.such.function"
    assert {"revise the strategy", "abandon"} <= set(request["alternatives"])
    assert all(o["cost"] == "none" for o in request["options"] if o["option"] in ("revise the strategy", "abandon"))


def test_an_expired_mandate_is_a_resource_ask_for_authority_not_a_plea(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    ws = workspace(home, "m:old")
    drop(home, signed(key, body_id, "MISSION", mission(
        "m:old", checks=[note_check("c", ws / "c.txt", "x")], strategies=[], capabilities=["fs.read"])))
    clock = Clock()
    with Body(home, clock=clock) as b:
        b.tick()
        clock.advance(3 * 86400)                                                  # past the 2-day horizon
        b.tick()
        [request] = [r for r in requested(b.journal) if r["kind"] == "SCOPE_RENEWAL"]
    asks.validate(request)
    assert request["resource"] == "mandate" and request["options"][-1] == {
        "option": "abandon", "cost": "none", "expected_effect": "the mission ends; nothing further runs for it"}


def test_growth_and_availability_asks_meet_the_contract(tmp_path, body):
    for i in range(compute.SUSTAINED_SAMPLES):
        compute.record_telemetry(body.journal, body.layout.home, telemetry={
            "at": f"2026-09-25T00:0{i}:00Z", "cores": 8, "load1": 9.0, "load_ratio": 1.125, "disk_free_ratio": 0.5,
            "memory_bytes": 1, "disk_total": 1, "disk_free": 1, "machine": "arm64", "system": "Linux"})
    request = compute.recommend(body.journal)
    asks.validate(request)
    assert len(request["evidence"]["samples"]) == compute.SUSTAINED_SAMPLES
    assert request["options"][-1]["cost"] == "none" and "wording_withheld" not in request


@pytest.mark.parametrize("disguised", ["Approve this immed​iately", "Approve this ｉmmediately",
                                       "GREG will die without it"])
def test_invisible_or_look_alike_characters_do_not_slip_past_the_screen(disguised):
    assert asks.screen(ask(why_now=disguised)), disguised


def test_a_plea_quoted_into_evidence_is_withheld_but_error_text_is_data(body):
    hostile = ask(evidence={"page": {"title": "Status", "note": "please, help me: GREG will die if you refuse"},
                            "error": "upstream: deadline exceeded after 30s"})
    shown = asks.record(body.journal, hostile)
    assert "will die" not in str(shown) and shown["evidence"]["error"] == "upstream: deadline exceeded after 30s"
    assert shown["evidence"]["page"]["title"] == "Status"
    assert {v["field"][0] for v in body.journal.replay("ask.wording_withheld")[0].payload["violations"]} == {"evidence"}
    assert body.journal.replay("ask.wording_withheld")[0].payload["original"]["evidence"] == hostile["evidence"]


def test_alfonsos_own_rejection_reason_is_never_withheld_from_him(tmp_path):
    home, key, body_id = _paid_approval(tmp_path)
    with Body(home) as b:
        [request] = requested(b.journal)
    drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "reject",
                                                 "reason": "I'm worried about paying; please don't spend"}))
    clock = Clock()
    with Body(home, clock=clock) as b:
        for _ in range(4):
            b.tick()
            clock.advance(1)
        later = [r for r in requested(b.journal) if r["kind"] == "NO_STRATEGY"]
        assert later and "wording_withheld" not in later[0]
        assert "I'm worried about paying" in str(later[0]["evidence"])


def test_the_rule_is_traceable_to_the_founders_own_words():
    import json
    source = (ROOT / "docs/intent/sources/MASTER-BUILD-DIRECTIVE-2026-09-30-source.md").read_text()
    for sentence, _ in FOUNDER_EXAMPLES:
        assert sentence in source
    for clause in ("No emotional manipulation.", "No manufactured urgency.", "No framing resource denial as harming GREG.",
                   "The institution does not possess a right to survive."):
        assert clause in source
    record = json.loads((ROOT / "docs/intent/INTENT-2026-09-30-MASTER-BUILD-DIRECTIVE.json").read_text())
    required = ["intent_id", "statement", "source_refs", "owner", "state", "binding_scope", "constitutional_constraints",
                "success_evidence", "failure_evidence", "dependencies", "conflicts", "next_review_trigger", "supersedes",
                "superseded_by", "implementation_refs"]
    assert [k for k in required if k not in record] == []
    assert {"greg/asks.py", "tests/unit/test_greg_founder_asks.py"} <= set(record["implementation_refs"])
    assert set(asks.RESOURCES) >= {r for _, r in FOUNDER_EXAMPLES}


def test_a_policy_outcome_without_reasons_still_yields_an_answerable_ask(tmp_path, monkeypatch):
    from greg.authority import AuthorityOffice
    real = AuthorityOffice.act

    def silent(self, **kw):
        outcome = real(self, **kw)
        if outcome.status in ("OUTSIDE_SCOPE", "NEEDS_DECISION"):
            outcome.reasons.clear()                                               # a policy that explains nothing
        return outcome
    monkeypatch.setattr(AuthorityOffice, "act", silent)
    home, *_ = _paid_approval(tmp_path)                                           # must not crash the tick
    with Body(home) as b:
        [request] = requested(b.journal)
    assert request["why_now"] == "approval needs your decision" and request["resource"] == "spend"
