"""A check the receipt's prefix cannot decide is decided over the whole output the receipt kept (directive of
2026-10-22, section VI: "full-document capability"; section VIII: "a preview is not a result").

``authority.keep_output`` cuts a receipt's long strings to 16 KiB and its lists to 1000 items, and keeps the whole
output (up to 1 MiB of canonical JSON) in the body's content-addressed artifact store, recording its address on the
receipt. The judge (``3d2f9cc4``, ``af6fdfe1``) proves from the kept part only what it can, and calls the rest
INSUFFICIENT, so a phrase past 16 KiB used to cost the founder a SENSOR_FAILURE ask. ``judge_receipt`` now decides
such a check over the whole output, read only by the ledger's recorded address, re-hashed on read and checked to
cut to exactly the kept output. A missing, altered or foreign artifact decides nothing. The engine, the refusal
watch, the appraiser's re-derivation and precondition check, and Goal Gravity all read a receipt this way.

In-process Body with a test clock and a per-test founder key, not Alfonso's (SANDBOX).
"""
from __future__ import annotations

import json
import unicodedata

import pytest

import greg.authority
from greg.artifacts import ArtifactStore
from greg.authority import RECEIPT_LIST_LIMIT, RECEIPT_TEXT_LIMIT, bounded, keep_output, output_store
from greg.body import Body
from greg.missions import FALSE, INSUFFICIENT, TRUE, evaluate_receipt, judge, judge_receipt
from tests.greg_fixtures import Clock, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_missions import events, run, submit

FILLER = "proof settlement notice delivery party shall net due. " * 400       # about 22 KiB, no test phrase
assert len(FILLER) > RECEIPT_TEXT_LIMIT + 4000
PHRASE = "terminate without notice"
assert PHRASE not in FILLER


def receipt(output, root):
    """A receipt result as authority.AuthorityOffice writes it: the kept output, and the whole one's record."""
    kept, whole = keep_output(output, root)
    return {"output": kept, **({"output_artifact": whole} if whole else {})}


def p(op, value, field="text"):
    return {"op": op, "field": field, "value": value}


# -- sections VI.1-VI.7: phrases before, after and across the cut; missing phrases; equality ----------------------

def test_a_phrase_inside_the_prefix_is_decided_by_the_receipt_alone(tmp_path):
    result = receipt({"text": PHRASE + ". " + FILLER}, tmp_path)
    verdict, detail = judge_receipt(p("contains", PHRASE), result, None)      # no store needed: the prefix proves it
    assert verdict == TRUE and "whole output" not in detail


def test_a_phrase_past_the_prefix_is_found_in_the_whole_output(tmp_path):
    result = receipt({"text": FILLER + PHRASE}, tmp_path)
    assert judge(p("contains", PHRASE), result["output"])[0] == INSUFFICIENT     # the prefix alone: unknown
    verdict, detail = judge_receipt(p("contains", PHRASE), result, tmp_path)
    assert verdict == TRUE and "decided over the whole output kept at sha256:" in detail
    assert evaluate_receipt(p("contains", PHRASE), result, tmp_path)[0] is True


def test_a_forbidden_phrase_past_the_prefix_is_proved_present(tmp_path):
    result = receipt({"text": FILLER + "Either party may " + PHRASE + "."}, tmp_path)
    assert judge_receipt(p("not_contains", PHRASE), result, tmp_path)[0] == FALSE
    passed, detail = evaluate_receipt(p("not_contains", PHRASE), result, tmp_path)
    assert passed is False and not detail.startswith("insufficient evidence")


def test_a_match_spanning_the_cut_is_decided_over_the_whole(tmp_path):
    text = "x" * (RECEIPT_TEXT_LIMIT - 5) + PHRASE + FILLER                  # straddles character 16384
    result = receipt({"text": text}, tmp_path)
    assert judge(p("contains", PHRASE), result["output"])[0] == INSUFFICIENT
    assert judge_receipt(p("contains", PHRASE), result, tmp_path)[0] == TRUE
    assert judge_receipt(p("not_contains", PHRASE), result, tmp_path)[0] == FALSE


def test_a_missing_phrase_is_false_on_complete_text_and_on_a_kept_whole(tmp_path):
    assert judge_receipt(p("contains", PHRASE), receipt({"text": "short and clean"}, tmp_path), tmp_path)[0] == FALSE
    long = receipt({"text": FILLER}, tmp_path)
    assert judge_receipt(p("contains", PHRASE), long, None)[0] == INSUFFICIENT     # no whole readable: unknown
    assert judge_receipt(p("contains", PHRASE), long, tmp_path)[0] == FALSE       # whole read: absent
    assert judge_receipt(p("not_contains", PHRASE), long, tmp_path)[0] == TRUE


def test_equality_of_a_long_string_agrees_by_digest_and_over_the_whole(tmp_path):
    text = FILLER + "end"
    result = receipt({"text": text}, tmp_path)
    assert judge_receipt(p("equals", text), result, None)[0] == TRUE                  # digest and length
    assert judge_receipt(p("equals", text[:-1] + "x"), result, tmp_path)[0] == FALSE
    assert judge_receipt(p("equals", text[:RECEIPT_TEXT_LIMIT]), result, tmp_path)[0] == FALSE


# -- the invariant: over a kept whole, a long output is judged as the same value uncut ----------------------------

LONG_ROWS = [f"row{i}" for i in range(RECEIPT_LIST_LIMIT + 500)]
CASES = [
    ({"text": FILLER + PHRASE}, [p("contains", PHRASE), p("not_contains", PHRASE), p("contains", "absent clause"),
                                 p("not_contains", "absent clause"), p("count_gte", len(FILLER)),
                                 p("equals", FILLER + PHRASE), {"op": "exists", "field": "text"}]),
    ({"rows": LONG_ROWS}, [p("contains", "row1200", "rows"), p("not_contains", "row1200", "rows"),
                           p("not_contains", "row9999", "rows"), p("count_gte", 1500, "rows"),
                           p("count_gte", 1501, "rows"), p("equals", LONG_ROWS, "rows"),
                           {"op": "exists", "field": "rows.1200"}, {"op": "absent", "field": "rows.1600"}]),
    ({"items": ["short", FILLER + PHRASE]}, [p("contains", FILLER + PHRASE, "items"),
                                             p("not_contains", FILLER + PHRASE, "items"),
                                             p("equals", ["short", FILLER + PHRASE], "items"),
                                             p("contains", "short", "items")]),
    ({"doc": {"title": "t", "body": FILLER + PHRASE}}, [p("contains", PHRASE, "doc.body"),
                                                       p("not_contains", PHRASE, "doc.body"),
                                                       p("equals", FILLER + PHRASE, "doc.body")]),
    ({"text": "é" * (RECEIPT_TEXT_LIMIT + 10) + "naïve résumé"}, [p("contains", "naïve résumé"),
                                                                  p("not_contains", "naïve résumé")]),
    # one text in either normalization form, over a cut or not (tests/unit/test_greg_faithful_text.py)
    ({"text": FILLER + unicodedata.normalize("NFD", "café")}, [p("contains", unicodedata.normalize("NFD", "café")),
                                                               p("contains", "café"), p("not_contains", "café")]),
]


@pytest.mark.parametrize("output, predicates", CASES, ids=["text", "list", "member", "nested", "multibyte", "nfd"])
def test_over_a_kept_whole_the_verdict_is_the_verdict_on_the_value_uncut(tmp_path, output, predicates):
    result = receipt(output, tmp_path)
    assert result["output"] != output and result["output_artifact"]["address"]      # the receipt did cut it
    for predicate in predicates:
        uncut = judge(predicate, output, whole=True)[0]
        assert uncut != INSUFFICIENT
        assert judge_receipt(predicate, result, tmp_path)[0] == uncut, predicate


AT_LIMIT = LONG_ROWS[:RECEIPT_LIST_LIMIT]


@pytest.mark.parametrize("beside", ["", FILLER], ids=["nothing-cut", "a-cut-string"])
def test_a_list_at_the_limit_reads_the_same_kept_whole_or_re_read(tmp_path, beside):
    """A list of exactly the item limit may have been cut there by the capability itself (fs.list cuts its listing
    there and says nothing), so no mode decides what lies past it: the engine over the kept whole, the appraiser's
    re-derivation and its fresh re-reading agree. Before, a whole read from the store took it as all of it, and the
    same list closed the mission or stayed undecided by the length of an unrelated field (review of #209, F1)."""
    output = {"rows": AT_LIMIT, "text": beside}
    result = receipt(output, tmp_path)
    undecided = [p("not_contains", "row1200", "rows"), p("contains", "row1200", "rows"),
                 p("count_gte", RECEIPT_LIST_LIMIT + 1, "rows"), p("equals", AT_LIMIT, "rows"),
                 {"op": "absent", "field": "rows.1200"}]
    for predicate in undecided:
        assert judge_receipt(predicate, result, tmp_path)[0] == INSUFFICIENT, predicate     # the engine, kept whole
        assert judge(predicate, output)[0] == INSUFFICIENT, predicate                      # the fresh re-reading
        assert judge(predicate, output, whole=True)[0] == INSUFFICIENT, predicate
    for predicate, verdict in [(p("contains", "row999", "rows"), TRUE), (p("not_contains", "row5", "rows"), FALSE),
                               (p("count_gte", RECEIPT_LIST_LIMIT, "rows"), TRUE),
                               (p("equals", AT_LIMIT[:-1], "rows"), FALSE)]:
        assert judge_receipt(predicate, result, tmp_path)[0] == judge(predicate, output)[0] == verdict, predicate


# -- section VI.8: malformed encoding -------------------------------------------------------------------------------

def test_a_lone_surrogate_past_the_cut_no_longer_fails_the_action_and_is_judged(tmp_path):
    # JSON from an untrusted tool or MCP server can carry "\ud800"; bounded() used to raise on it, so the Gate
    # recorded a read-only sensor as "reconciliation_required" and the founder was asked whether a read executed.
    text = json.loads('"' + "a" * (RECEIPT_TEXT_LIMIT + 50) + '\\ud800 tail"')
    result = receipt({"text": text}, tmp_path)
    assert result["output"]["text"]["length"] == len(text)
    assert judge_receipt(p("contains", "tail"), result, tmp_path)[0] == TRUE
    assert judge_receipt(p("equals", text), result, None)[0] == TRUE                  # the digest path agrees


# -- section VI.9 and VI.13: missing, damaged, foreign or forged evidence decides nothing --------------------------

@pytest.mark.parametrize("damage", ["deleted", "altered", "not json", "foreign", "no store", "store refused"])
def test_damaged_or_foreign_evidence_never_decides(tmp_path, damage, monkeypatch):
    result = receipt({"text": FILLER + PHRASE}, tmp_path)
    address = result["output_artifact"]["address"]
    store = output_store(tmp_path)
    root = tmp_path
    if damage == "deleted":
        store.path(address).unlink()
    elif damage == "altered":
        store.path(address).write_bytes(store.path(address).read_bytes().replace(b"notice", b"nothing"))
    elif damage == "not json":
        store.path(address).write_bytes(b"\x00not json")
    elif damage == "foreign":                    # a valid artifact of another output, under the receipt's address
        other = receipt({"text": FILLER + "a different " + PHRASE + "!"}, tmp_path)
        result["output_artifact"] = other["output_artifact"]
    elif damage == "no store":
        root = None
    elif damage == "store refused":
        monkeypatch.setattr(greg.authority, "OUTPUT_ARTIFACT_BYTES", 64)
        result = receipt({"text": FILLER + PHRASE}, tmp_path / "small")
        assert result["output_artifact"]["address"] is None
    for op in ("contains", "not_contains"):
        verdict, detail = judge_receipt(p(op, PHRASE), result, root)
        assert verdict == INSUFFICIENT, (damage, op, detail)


def test_an_output_cannot_supply_its_own_artifact_record(tmp_path):
    # only the AuthorityOffice writes output_artifact beside the output; a key inside the output is just data
    output = {"text": FILLER + PHRASE, "output_artifact": {"address": "sha256:" + "0" * 64}}
    result = receipt(output, tmp_path)
    result.pop("output_artifact")
    assert judge_receipt(p("contains", PHRASE), result, tmp_path)[0] == INSUFFICIENT


# -- section VI.10: an output that declares itself incomplete stays monotone-only, whole or not ---------------------

def test_a_declared_incomplete_output_stays_monotone_over_its_whole(tmp_path):
    # e.g. document.text on a partly scanned PDF: the text it extracted is whole, the document is not
    result = receipt({"text": FILLER + PHRASE, "complete": False, "found": None}, tmp_path)
    assert judge_receipt(p("contains", PHRASE), result, tmp_path)[0] == TRUE
    assert judge_receipt(p("not_contains", "absent clause"), result, tmp_path)[0] == INSUFFICIENT
    assert judge_receipt(p("equals", False, "complete"), result, tmp_path)[0] == TRUE


# -- on the mission path (sections VI.2, VI.3, VI.11, VI.12, VI.14) -------------------------------------------------

def _contract(data, text, name="contract.txt"):
    path = data / name
    path.write_text(text)
    return path


def _forbid(check_id, path, text):
    check = note_check(check_id, path, text)
    check["predicate"]["op"] = "not_contains"
    return check


def test_a_required_phrase_past_16_kib_closes_the_mission_without_asking_and_is_verified(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    contract = _contract(data, FILLER + "The renewal term is twelve months.")
    submit(home, key, body_id, "MISSION", mission("m:term", checks=[note_check("term", contract, "twelve months")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=4)
    assert missions["m:term"].status == "ACHIEVED"
    assert not [r for r in requests if r.get("mission_id") == "m:term"]           # before: a SENSOR_FAILURE ask
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:term"]
    assert observed[-1]["passed"] and "decided over the whole output" in observed[-1]["detail"]
    appraised = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:term"]
    assert appraised and appraised[-1]["verdict"] == "VERIFIED"                  # the separate appraiser agrees


def test_an_altered_artifact_makes_the_appraiser_refute_the_closure(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    contract = _contract(data, FILLER + "The renewal term is twelve months.")
    submit(home, key, body_id, "MISSION", mission("m:term", checks=[note_check("term", contract, "twelve months")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    run(home, Clock(), ticks=4)
    with Body(home) as body:
        assert body.appraise("m:term")["verdict"] == "VERIFIED"
        stored = list((body.layout.artifacts / greg.authority.OUTPUT_ARTIFACT_DIR).rglob("*"))
        for path in (q for q in stored if q.is_file()):
            path.write_bytes(path.read_bytes().replace(b"twelve months", b"twelve monkey"))
        verdict = body.appraise("m:term")
    assert verdict["verdict"] == "REFUTED" and verdict["checks"]["checks_rederived_from_receipts"] is False


def test_a_forbidden_phrase_past_16_kib_is_decided_failing_not_asked(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    contract = _contract(data, FILLER + "Either party may terminate without notice.")
    submit(home, key, body_id, "MISSION", mission("m:clean", checks=[_forbid("clean", contract, PHRASE)],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    clock = Clock()
    missions, requests = run(home, clock, ticks=4, step=600.0)
    assert missions["m:clean"].status != "ACHIEVED"
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:clean"]
    assert observed and all(not e["passed"] and not e["detail"].startswith("sensor inconclusive") for e in observed)
    # a measured failure with no strategy to change it: the founder decides what to do (NO_STRATEGY), and is not
    # asked whether the sensor works (before: SENSOR_FAILURE)
    assert [r.get("kind") for r in requests if r.get("mission_id") == "m:clean"] == ["NO_STRATEGY"]
    contract.write_text(FILLER + "Notice periods apply to both parties.")       # the world changes
    missions, _ = run(home, clock, ticks=6, step=600.0)
    assert missions["m:clean"].status == "ACHIEVED"


def test_an_incomplete_observation_is_kept_and_a_restarted_body_decides_the_next_one(tmp_path, monkeypatch):
    home, key, body_id, data = make_body(tmp_path)
    contract = _contract(data, FILLER + "The renewal term is twelve months.")
    submit(home, key, body_id, "MISSION", mission("m:term", checks=[note_check("term", contract, "twelve months")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    clock = Clock()
    monkeypatch.setattr(greg.authority, "OUTPUT_ARTIFACT_BYTES", 64)               # no whole kept: prefix only
    missions, _ = run(home, clock, ticks=2)
    assert missions["m:term"].status != "ACHIEVED"
    first = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:term"]
    assert first and first[0]["detail"].startswith("sensor inconclusive (incomplete evidence)")
    monkeypatch.undo()                                                            # a restarted body keeps outputs
    missions, _ = run(home, clock, ticks=6, step=600.0)
    assert missions["m:term"].status == "ACHIEVED"
    after = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:term"]
    assert after[: len(first)] == first                                           # the old reading is not rewritten
    assert after[-1]["passed"] and "decided over the whole output" in after[-1]["detail"]


def test_no_closure_while_any_required_check_is_unproven(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    decided = _contract(data, FILLER + "The renewal term is twelve months.")
    # 200 KiB of control characters: its canonical JSON is over 1 MiB, so the store refuses the whole (realistic)
    too_big = _contract(data, "\x01" * (200 * 1024) + "needle", name="dump.txt")
    submit(home, key, body_id, "MISSION", mission("m:both", checks=[note_check("term", decided, "twelve months"),
                                                                     note_check("dump", too_big, "needle")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=8, step=600.0)
    assert missions["m:both"].status != "ACHIEVED"
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:both"]
    assert any(e["check_id"] == "term" and e["passed"] for e in observed)
    dump = [e for e in observed if e["check_id"] == "dump"]
    assert dump and all(not e["passed"] and e["detail"].startswith("sensor inconclusive") for e in dump)
    assert any(r.get("kind") == "SENSOR_FAILURE" for r in requests if r.get("mission_id") == "m:both")


def test_a_precondition_decided_over_the_whole_gates_the_strategy_and_the_appraiser_agrees(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    approval = _contract(data, FILLER + "Status: approved for release.")
    note = workspace(home, "m:gated") / "release.txt"
    check_ok = note_check("approved", approval, "approved for release")
    spec = mission("m:gated", checks=[check_ok, note_check("released", note, "released")],
                   strategies=[write_strategy("ship", "release.txt", "released", ["released"],
                                              requires=["approved"])],
                   capabilities=["fs.read", "fs.write"])
    submit(home, key, body_id, "MISSION", spec)
    missions, requests = run(home, Clock(), ticks=8)
    assert missions["m:gated"].status == "ACHIEVED" and note.read_text() == "released"
    assert not [r for r in requests if r.get("mission_id") == "m:gated"]
    appraised = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:gated"]
    assert appraised[-1]["verdict"] == "VERIFIED" and appraised[-1]["checks"]["preconditions_honored"] is True


def test_one_unmeasurable_check_beside_a_passing_one_still_reaches_the_founder(tmp_path):
    """Pre-existing on #196 190c58fb, independent of output size: the SENSOR_FAILURE streak counted only an unbroken
    run of unmeasured readings, and the passing check's reading broke it every tick. Twenty ticks of ten minutes
    re-observed forever and asked nothing; the same unmeasurable check alone was asked about."""
    home, key, body_id, data = make_body(tmp_path)
    ok = _contract(data, "all good", name="ok.txt")
    big = data / "big.txt"
    big.write_bytes(b"x" * (300 * 1024))                         # over fs.read's 256 KiB ceiling: the read fails
    submit(home, key, body_id, "MISSION", mission("m:two", checks=[note_check("ok", ok, "good"),
                                                                    note_check("big", big, "needle")],
                                                  strategies=[], capabilities=["fs.read"], ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=20, step=600.0)
    assert missions["m:two"].status != "ACHIEVED"
    asks = [r for r in requests if r.get("mission_id") == "m:two"]
    assert [r.get("kind") for r in asks] == ["SENSOR_FAILURE"]


def test_goal_gravity_reads_a_long_observation_as_the_engine_decided_it(tmp_path, monkeypatch):
    """Goal Gravity recomputes each observation from its own receipt and calls a disagreement untrusted. Read from
    the prefix alone, a check the engine decided over the whole output would disagree and be distrusted."""
    from greg import goal_gravity as gg
    from tests.unit.test_greg_goal_gravity import MID, World
    monkeypatch.setattr(Body, "_close_out", lambda self, now: None)      # as the goal-gravity suite's `fast`
    world = World(tmp_path)
    world.ws.mkdir(parents=True, exist_ok=True)
    (world.ws / "c.txt").write_text(FILLER + " ok")                      # long; the phrase only past the cut
    world.start()
    world.tick(3)
    assert (world.ws / "c.txt").read_text() == FILLER + " ok"            # decided passing: not "repaired"
    with world.body() as b:
        belief = gg.binding_for(b).loop.world.belief(MID, "c")
    assert belief is not None and belief.value is True and belief.trust_level == "attributed"


def test_a_refusal_written_past_16_kib_of_a_note_is_honored(tmp_path):
    """A person's decline (shared work, N6) may come as a long pasted thread. Read from the prefix alone the
    refusal was inconclusive, so GREG kept waiting on the person; over the kept whole it is heard and honored."""
    from tests.unit.test_greg_shared_work import REF, asks, start, tick
    home, key, body_id, clock, body, mid, folder = start(tmp_path)
    try:
        assert asks(body, mid)[-1]["action_id"] == "agree-terms"
        (folder / "declined.txt").write_text(FILLER + f"\nDana declines {REF}: no capacity this month\n")
        tick(body, clock, 4)
        [honored] = [e.payload for e in body.journal.replay("human.refusal_honored")]
        assert honored["action_id"] == "agree-terms" and honored["evidence"]
        observed = [e.payload for e in body.journal.replay("human.refusal_observed")]
        assert observed[-1]["declined"] is True and observed[-1]["inconclusive"] is False
    finally:
        body.close()


def test_a_fact_past_16_kib_of_a_pdfs_text_closes_with_a_plain_check(tmp_path):
    """With #201's document.text: the founder's check reads the extracted text itself (no `phrase` parameter, no
    capability-specific field). A fact past the receipt's 16 KiB decides over the whole extraction the receipt kept;
    before, only a check written against `found` could close. Skips where #201 or poppler is absent."""
    documents = pytest.importorskip("greg.documents")
    from greg import genesis as genesis_mod
    if genesis_mod.installed_binary("pdftotext") is None:
        pytest.skip("pdftotext not installed on this body")
    home, key, body_id, data = make_body(tmp_path)
    lease = data / "long.pdf"
    filler = [[" ".join(["proof", "settlement", "notice", "delivery", "party", "shall", "net", "due"])] * 40] * 8
    lease.write_bytes(documents.write_pdf(filler + [["The renewal term is twelve months."]], compress=True))
    check = {"check_id": "states", "description": "long.pdf states the renewal term",
             "sensor": {"function": "document.text", "params": {"path": str(lease)}, "target": "fs:long.pdf"},
             "predicate": {"op": "contains", "field": "text", "value": "renewal term is twelve months"}}
    submit(home, key, body_id, "MISSION", mission("m:pdf", checks=[check], strategies=[],
                                                  capabilities=["fs.read", "acquired.document.text.*"],
                                                  ceiling="read_only", auto_attach=True))
    missions, requests = run(home, Clock(), ticks=4)
    assert missions["m:pdf"].status == "ACHIEVED"
    assert not [r for r in requests if r.get("mission_id") == "m:pdf"]
    observed = [e for e in events(home, "mission.observed") if e["mission_id"] == "m:pdf"]
    assert observed[-1]["passed"] and "decided over the whole output" in observed[-1]["detail"]


# -- review of #209 ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("predicate", [p("contains", 5), p("not_contains", ["a"]), p("count_gte", "many"),
                                       p("gte", "3"), p("lte", None)])
def test_a_signed_value_of_another_type_fails_the_check_and_never_crashes_the_tick(tmp_path, predicate):
    """contains 5 over a text, count_gte "many": the operation does not apply, so the check fails. Over the whole
    output read from the store it used to raise TypeError, which ended Body.tick (review of #209); over a short text
    it always had."""
    long = receipt({"text": FILLER + PHRASE}, tmp_path)
    assert judge_receipt(predicate, long, tmp_path)[0] == FALSE
    assert judge(predicate, {"text": "short"})[0] == FALSE
    assert judge(predicate, {"text": FILLER + PHRASE}, whole=True)[0] == FALSE
    assert judge({**predicate, "field": "n"}, {"n": 3})[0] == FALSE                 # a number, against a non-number


NESTED = [
    # a 1500-item list beside a cut string, asked whether it contains its own first 1000 items as one member
    ({"batches": [[f"id{i}" for i in range(1500)]], "log": FILLER},
     p("contains", [f"id{i}" for i in range(1000)], "batches")),
    # a list of records, one of which holds a long string
    ({"rows": [{"t": FILLER + PHRASE}]}, p("not_contains", {"t": FILLER + PHRASE}, "rows")),
    ({"rows": [{"t": FILLER + PHRASE}]}, p("contains", {"t": FILLER + PHRASE}, "rows")),
    ({"rows": [{"t": FILLER + PHRASE}]}, p("contains", {"t": FILLER}, "rows")),
    # an object holding a long string, and a list whose first member is long beside 1299 short ones
    ({"doc": {"title": "t", "body": FILLER + PHRASE}}, p("equals", {"title": "t", "body": FILLER + PHRASE}, "doc")),
    ({"doc": {"title": "t", "body": FILLER + PHRASE}}, p("equals", {"title": "t", "body": FILLER}, "doc")),
    ({"rows": [FILLER] + [str(i) for i in range(1299)]}, p("equals", [FILLER] + [str(i) for i in range(1299)], "rows")),
    ({"grid": [[str(i) for i in range(1500)], ["x"]]}, p("equals", [[str(i) for i in range(1500)], ["x"]], "grid")),
    ({"grid": [[str(i) for i in range(1500)], ["x"]]}, p("equals", [[str(i) for i in range(1000)], ["x"]], "grid")),
]


@pytest.mark.parametrize("output, predicate", NESTED)
def test_a_cut_below_the_judged_value_never_decides_as_its_wrapper(tmp_path, output, predicate):
    """A long string or a list at the item limit below the judged value's own members used to be compared as the
    receipt's prefix record: a wrong TRUE (the first case) and wrong FALSEs, and judge_receipt, which reads the
    kept whole only for an undecided verdict, kept them (review of #209). What the kept part decides is now right,
    and the rest is decided over the kept whole."""
    result = receipt(output, tmp_path)
    truth = judge(predicate, output, whole=True)[0]
    assert truth != INSUFFICIENT
    assert judge(predicate, result["output"])[0] in (truth, INSUFFICIENT), predicate
    assert judge_receipt(predicate, result, tmp_path)[0] == truth, predicate


def test_a_reading_reused_after_a_restart_keeps_the_whole_output_its_receipt_kept(tmp_path):
    """A body stopped between a sensor's receipt and its observation reuses that receipt. The reused outcome used to
    drop the receipt's record of the whole output, so the same reading was judged on its prefix alone: inconclusive
    where the fresh reading had decided (review of #209)."""
    home, key, body_id, data = make_body(tmp_path)
    page = data / "page.txt"
    page.write_text(FILLER + PHRASE)
    check = note_check("c", page, PHRASE)
    spec = mission("m:reuse", checks=[check], strategies=[write_strategy("w", "w.txt", "x", ["c"])],
                   capabilities=["fs.read", "fs.write"])
    with Body(home) as body:
        body.apply(signed(key, body_id, "MISSION", spec), channel="inbox")
        state = body.engine.book.missions["m:reuse"]
        manifest, adapter, _ = body.engine._resolve(check["sensor"])

        def read():
            return body.office.act(
                mission_id=state.mission_id, cone=state.cone, command_digest=state.command_digest, manifest=manifest,
                adapter=adapter, ctx=body.engine._context(state, manifest), params=check["sensor"]["params"],
                target=check["sensor"]["target"], cost_usd=0.0, expected_outcome="observation captured",
                evidence_refs=[], attempt="0@restart", spent_usd=0.0, approved_scopes=set())

        first, again = read(), read()
        artifacts = body.engine.artifact_root
    assert again.reasons == ["retained receipt reused after restart"] and again.receipt_hash == first.receipt_hash
    assert first.output_artifact["address"] and again.output_artifact == first.output_artifact
    assert evaluate_receipt(check["predicate"], {"output": again.output, "output_artifact": again.output_artifact},
                            artifacts) == evaluate_receipt(check["predicate"], {
                                "output": first.output, "output_artifact": first.output_artifact}, artifacts)
    assert evaluate_receipt(check["predicate"], {"output": again.output, "output_artifact": again.output_artifact},
                            artifacts)[0] is True


def test_the_appraiser_re_derives_a_bind_by_artifact_from_the_whole_output(tmp_path):
    """A strategy that bound a long value by artifact closes its mission; the separate appraiser re-derives the params
    the engine handed the Gate and used to read only the kept prefix, so it refuted a correct closure ("completed
    action lacks its signed strategy's Gate receipt"; review of #209)."""
    from tests.unit.test_greg_artifact_bind import start, tick
    home, root = start(tmp_path)
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert tick(body, clock, 8)[-1] == "ACHIEVED"
        appraised = body.appraise("m:big")
    assert appraised["verdict"] == "VERIFIED", appraised["findings"]        # before: REFUTED
    assert appraised["checks"]["exactly_once"] is True


def test_a_check_on_a_record_another_receipt_kept_closes_and_is_verified(tmp_path):
    """A mission whose check reads, through pipeline.inspect, the digest of a 22 KiB text an earlier action read: the
    inspecting receipt cut nothing, so the record it returned is its data. J9 had refused to step into it: the
    founder was asked about a sensor failure, and the appraiser refuted the closure the base verified (review of
    #209, APR-1)."""
    import hashlib
    home, key, body_id, data = make_body(tmp_path)
    page = data / "contract.txt"
    page.write_text(FILLER + PHRASE)
    check = {"check_id": "read_exact", "description": "the read action read exactly the signed contract",
             "sensor": {"capability": "pipeline.inspect", "target": "pipeline:read",
                        "params": {"action_id": "read", "field": "text", "type": "object"}},
             "predicate": {"op": "equals", "field": "value.sha256",
                           "value": hashlib.sha256((FILLER + PHRASE).encode()).hexdigest()}}
    strategy = {"action_id": "read", "capability": "fs.read", "params": {"path": str(page)},
                "target": "fs:contract.txt", "advances": ["read_exact"], "rationale": "read the contract"}
    submit(home, key, body_id, "MISSION", mission("m:pipe", checks=[check], strategies=[strategy],
                                                  capabilities=["fs.read", "pipeline.inspect"],
                                                  targets=("fs:*", "pipeline:*"), ceiling="read_only"))
    missions, requests = run(home, Clock(), ticks=10, step=600.0)
    assert missions["m:pipe"].status == "ACHIEVED", [r.get("kind") for r in requests]   # before: SENSOR_FAILURE
    [appraised] = [e for e in events(home, "mission.appraised") if e["mission_id"] == "m:pipe"]
    assert appraised["verdict"] == "VERIFIED", appraised["findings"]
