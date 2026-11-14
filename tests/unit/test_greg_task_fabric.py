"""Directive section 16: the Mind integrated with the existing Task Fabric, its worker lease and its evaluator.

Each test reproduced a defect before the change. A document work order (``worker.commission``, one lease) was
ACCEPTED by its independent evaluator (``worker.appraise``) whenever the deliverable file existed, and the
``daleobanks_post`` mission sent a worker's draft to the publish request on DALEOBANKS's figure-only check: a draft
that dropped its source's hedge or negation reached the publish request. The workers here are SCRIPTED TEST
DOUBLES that write fixed files; they test GREG's evaluator and authority rules, not worker capability.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import textwrap
from types import SimpleNamespace

import pytest

from greg import templates, workers
from greg.body import Body
from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
from greg.cognition.cortex import registry_view
from greg.cognition.settlement import _valid_receipt
from tests.greg_fixtures import Clock, drop, horizon, make_body, signed

SOURCE = ("A study at two depots found the new routing method may reduce delays by 12%. "
          "It did not lower fuel costs. Drivers at Northgate reported fewer missed windows.")
STUDY = "A study at two depots found the new routing method may reduce delays by 12%"
FUEL = "It did not lower fuel costs."
NAME = "Drivers at Northgate reported fewer missed windows."
FAITHFUL = [("A two-depot study found the routing method may cut delays by 12%.", STUDY),
            ("Fuel costs did not fall.", FUEL)]
CONTRACT = {"claims": "post.claims.json", "quality": "secondary", "expires_at": horizon(2)}


class Scripted:
    """Test double: writes fixed files. Never presented as a frontier worker."""
    name = "scripted-test-double"

    def __init__(self, files: dict):
        self.files, self.calls = files, 0

    def available(self):
        return True, ""

    def run(self, order, cwd):
        self.calls += 1
        for rel, text in self.files.items():
            (cwd / rel).parent.mkdir(parents=True, exist_ok=True)
            (cwd / rel).write_text(text)
        return workers.WorkerReport(self.name, self.name, 0, 0.1, 0.0, claim={"confidence": 1.0})


def files(claims, extra=""):
    draft = " ".join(text for text, _ in claims) + extra
    return {"post.txt": draft, "post.claims.json": json.dumps(
        [{"text": text, "quotes": [{"input": "source.txt", "quote": quote}]} for text, quote in claims])}


def ctx(tmp_path, capability, registry=None):
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=SecretBroker(tmp_path / "s.json"),
                             manifest=BUILTINS[capability][0], mission_id="m:test", grant_id="grant-test",
                             authority_ref="sha256:test", capability_registry=registry)


def order(tmp_path, *, contract=CONTRACT, allowed=("post.txt", "post.claims.json")):
    (tmp_path / "source.txt").write_text(SOURCE)
    acceptance = {"output": "post.txt", **({"bound_claims": contract} if contract else {})}
    return {"order": "depot-note", "mode": "document", "inputs": [str(tmp_path / "source.txt")],
            "objective": "Summarise the depot study.", "acceptance": acceptance, "allowed_paths": list(allowed),
            "provider": "scripted", "max_budget_usd": 1.0, "timeout_seconds": 60}


def rewrite_record(evidence, edit):
    """Edit the retained order and keep its recorded digests consistent: the attacker who can rewrite evidence.json
    rewrites the digests beside it too. #192's frozen-digest check alone then passes; the signed contract (#185)
    is what must still refuse."""
    record = json.loads(evidence.read_text())
    edit(record["order"])
    record["order_digest"] = record["summary"]["order_digest"] = workers.WorkOrder(**record["order"]).digest()
    evidence.write_text(json.dumps(record))


def commission_and_appraise(tmp_path, monkeypatch, worker_files, *, signed_contract=CONTRACT, registry=None, **kw):
    monkeypatch.setitem(workers.PROVIDERS, "scripted", Scripted(worker_files))
    workers.commission(order(tmp_path, **kw), ctx(tmp_path, "worker.commission"))
    params = {"order": "depot-note", **({"bound_claims": signed_contract} if signed_contract else {})}
    return workers.appraise(params, ctx(tmp_path, "worker.appraise", registry))


def test_before_the_change_a_distorted_document_was_accepted_and_without_the_contract_it_still_is(tmp_path, monkeypatch):
    """The preserved floor: an order signed without bound_claims is judged as before (the file exists)."""
    hedge = [("A two-depot study found the routing method cuts delays by 12%.", STUDY)]
    out = commission_and_appraise(tmp_path, monkeypatch, files(hedge), contract=None, signed_contract=None)
    assert out["verdict"] == "ACCEPTED" and "truth_preservation" not in out


def test_a_faithful_document_is_accepted_on_the_minds_receipts(tmp_path, monkeypatch):
    out = commission_and_appraise(tmp_path, monkeypatch, files(FAITHFUL))
    assert out["verdict"] == "ACCEPTED", out["findings"]
    truth, receipts = out["truth_preservation"], out["cognition_receipts"]
    assert truth["checked"] and truth["claims"] == 2 and truth["distortions"] == []
    assert "not entailment" in truth["limits"]
    assert all(_valid_receipt(r) and r["method"] == "cognition.evidence" and r["abstention_state"] == "NONE"
               for r in receipts.values())
    source = receipts["c1"]["proof_artifact"]["sources"][0]
    assert source["quality"] == "secondary" and "made before the worker ran" in source["provenance"]


@pytest.mark.parametrize("claims,kind", [
    ([("A two-depot study found the routing method cuts delays by 12%.", STUDY)], "certainty"),
    ([("It lowered fuel costs.", FUEL)], "negation"),
    ([("A study at all depots found the routing method may cut delays by 12%.", STUDY)], "scope"),
    ([("A two-depot study found the routing method may increase delays by 12%.", STUDY)], "direction"),
    ([("Drivers at Southgate reported fewer missed windows.", NAME)], "named_term"),
    ([("A two-depot study found the routing method may cut delays by 21%.", STUDY)], "figure"),
])
def test_a_document_that_changes_what_its_input_says_is_rejected_with_the_minds_reason(tmp_path, monkeypatch, claims, kind):
    out = commission_and_appraise(tmp_path, monkeypatch, files(claims))
    assert out["verdict"] == "REJECTED"
    assert kind in {d["class"] for d in out["truth_preservation"]["distortions"]}
    assert any("not supported as written" in f and "DISTORTION" in f for f in out["findings"])


def test_a_sentence_no_binding_covers_is_rejected(tmp_path, monkeypatch):
    out = commission_and_appraise(tmp_path, monkeypatch, files(FAITHFUL, " Drivers at Northgate loved it."))
    assert out["verdict"] == "REJECTED"
    assert any("no receipt covers" in f and "loved it" in f for f in out["findings"])


def test_a_document_without_its_claims_file_is_rejected(tmp_path, monkeypatch):
    out = commission_and_appraise(tmp_path, monkeypatch, {"post.txt": files(FAITHFUL)["post.txt"]})
    assert out["verdict"] == "REJECTED" and out["truth_preservation"]["checked"] is False
    assert any("claims file post.claims.json is missing" in f for f in out["findings"])


@pytest.mark.parametrize("claims_file,why", [
    ("not json", "not JSON"),
    ("[]", "1..32 claims"),
    (json.dumps([{"text": "Fuel costs did not fall.", "quotes": []}]), "no supporting span"),
    (json.dumps([{"text": "Fuel costs did not fall.", "quotes": [{"input": "other.txt", "quote": FUEL}]}]),
     "names one of the inputs"),
])
def test_malformed_bindings_are_findings_never_repaired(tmp_path, monkeypatch, claims_file, why):
    out = commission_and_appraise(tmp_path, monkeypatch, {"post.txt": "Fuel costs did not fall.",
                                                          "post.claims.json": claims_file})
    assert out["verdict"] == "REJECTED" and any(why in f for f in out["findings"])


def test_a_quote_the_input_does_not_contain_is_not_supported(tmp_path, monkeypatch):
    invented = [("Fuel costs did not fall.", "Fuel costs did not fall.")]       # cites its own words
    out = commission_and_appraise(tmp_path, monkeypatch, files(invented))
    assert out["verdict"] == "REJECTED" and any("not supported as written" in f for f in out["findings"])


def test_the_worker_cannot_make_a_distortion_supported_by_editing_its_copy_of_the_input(tmp_path, monkeypatch):
    """Even when the signer lets the worker write under inputs/, the Mind reads GREG's copy at the base commit."""
    edited = SOURCE.replace("may reduce", "reduces")
    claim = [("A two-depot study found the routing method reduces delays by 12%.",
              "A study at two depots found the new routing method reduces delays by 12%")]
    out = commission_and_appraise(tmp_path, monkeypatch, {**files(claim), "inputs/source.txt": edited},
                                  allowed=("post.txt", "post.claims.json", "inputs/*"))
    assert out["verdict"] == "REJECTED"
    assert any("not supported as written" in f for f in out["findings"])


def test_the_signed_contract_applies_when_the_record_is_edited(tmp_path, monkeypatch):
    """A record that drops bound_claims after commission neither weakens the standard nor goes unnoticed."""
    hedge = [("A two-depot study found the routing method cuts delays by 12%.", STUDY)]
    monkeypatch.setitem(workers.PROVIDERS, "scripted", Scripted(files(hedge)))
    workers.commission(order(tmp_path), ctx(tmp_path, "worker.commission"))
    evidence = tmp_path / "ws" / "work-orders" / "depot-note" / "evidence.json"
    pristine = evidence.read_text()
    # a plain edit breaks the record's frozen digest (#192) and is refused before any evaluation
    record = json.loads(pristine)
    del record["order"]["acceptance"]["bound_claims"]
    evidence.write_text(json.dumps(record))
    out = workers.appraise({"order": "depot-note", "bound_claims": CONTRACT}, ctx(tmp_path, "worker.appraise"))
    assert out["verdict"] == "REJECTED" and out["findings"] == ["retained work order does not match its frozen digest"]
    # an edit that also rewrites the digests passes that check; the contract signed into the mission still applies
    evidence.write_text(pristine)
    rewrite_record(evidence, lambda o: o["acceptance"].pop("bound_claims"))
    out = workers.appraise({"order": "depot-note", "bound_claims": CONTRACT}, ctx(tmp_path, "worker.appraise"))
    assert out["verdict"] == "REJECTED"
    assert any("differs from the one this mission signed" in f for f in out["findings"])
    assert "certainty" in {d["class"] for d in out["truth_preservation"]["distortions"]}   # the Mind still ran


def test_an_edited_record_rejects_even_a_faithful_document(tmp_path, monkeypatch):
    monkeypatch.setitem(workers.PROVIDERS, "scripted", Scripted(files(FAITHFUL)))
    workers.commission(order(tmp_path), ctx(tmp_path, "worker.commission"))
    evidence = tmp_path / "ws" / "work-orders" / "depot-note" / "evidence.json"
    # the digests are rewritten with the edit, so the signed-contract comparison is what refuses (#185 on #192)
    rewrite_record(evidence, lambda o: o["acceptance"]["bound_claims"].update(quality="primary"))
    out = workers.appraise({"order": "depot-note", "bound_claims": CONTRACT}, ctx(tmp_path, "worker.appraise"))
    assert out["verdict"] == "REJECTED"
    assert any("differs from the one this mission signed" in f for f in out["findings"])


def test_a_quarantined_evidence_family_cannot_accept_a_document(tmp_path, monkeypatch):
    """The evaluator asks the Mind through the body's registry, so a founder's quarantine holds."""
    registry = registry_view(None)
    registry.set_state("cognition.evidence", "QUARANTINED")
    out = commission_and_appraise(tmp_path, monkeypatch, files(FAITHFUL), registry=registry)
    assert out["verdict"] == "REJECTED"
    assert all(r["abstention_state"] == "CAPABILITY_DEFICIT" for r in out["cognition_receipts"].values())


def test_the_lease_names_the_acceptance_contract_and_its_evaluator(tmp_path, monkeypatch):
    monkeypatch.setitem(workers.PROVIDERS, "scripted", Scripted(files(FAITHFUL)))
    workers.commission(order(tmp_path), ctx(tmp_path, "worker.commission"))
    lease = json.loads((tmp_path / "ws" / "work-orders" / "depot-note" / "lease.json").read_text())
    assert lease["acceptance"]["bound_claims"] == CONTRACT
    assert "cognition.evidence" in lease["evaluator"] and lease["authority_created"] is False
    prompt = workers.worker_prompt(workers.WorkOrder.from_params(order(tmp_path), ctx(tmp_path, "worker.commission")))
    assert "post.claims.json" in prompt and "source.txt" in prompt


@pytest.mark.parametrize("change,message", [
    ({"mode": "repository"}, "document work orders"),
    ({"allowed_paths": ["post.txt"]}, "must both be writable"),
    ({"bound_claims": {**CONTRACT, "quality": "certain"}}, "primary, secondary or unverified"),
    ({"bound_claims": {**CONTRACT, "extra": 1}}, "exactly claims, quality and expires_at"),
    ({"bound_claims": {**CONTRACT, "claims": "post.txt"}}, "beside the deliverable"),
    ({"bound_claims": {**CONTRACT, "expires_at": "soon"}}, "ISO time"),
])
def test_the_bound_claims_contract_is_validated_before_any_worker_runs(tmp_path, change, message):
    params = order(tmp_path)
    if "bound_claims" in change:
        params["acceptance"]["bound_claims"] = change["bound_claims"]
    if "allowed_paths" in change:
        params["allowed_paths"] = change["allowed_paths"]
    if "mode" in change:
        bound_claims = params["acceptance"]
        with pytest.raises(workers.WorkerError, match=message):
            workers.bound_claims(bound_claims, "repository", tuple(params["allowed_paths"]))
        return
    with pytest.raises(workers.WorkerError, match=message):
        workers.WorkOrder.from_params(params, ctx(tmp_path, "worker.commission"))


def test_inputs_are_decoded_as_utf8_whatever_the_bodys_locale(tmp_path, monkeypatch):
    """Non-ASCII text in GREG's copy of the input is read exactly, so a faithful quote of it is found."""
    monkeypatch.setitem(workers.PROVIDERS, "scripted", Scripted(files([("Café sales did not fall.",
                                                                        "Café sales did not fall.")])))
    params = order(tmp_path)
    (tmp_path / "source.txt").write_text("Café sales did not fall. Costs rose — by 3%.", encoding="utf-8")
    workers.commission(params, ctx(tmp_path, "worker.commission"))
    out = workers.appraise({"order": "depot-note", "bound_claims": CONTRACT}, ctx(tmp_path, "worker.appraise"))
    assert out["verdict"] == "ACCEPTED", out["findings"]


@pytest.mark.parametrize("target", ["post.txt", "inputs"])
def test_bytes_that_are_not_text_are_a_finding_never_a_crash(tmp_path, monkeypatch, target):
    worker_files = files(FAITHFUL)
    monkeypatch.setitem(workers.PROVIDERS, "scripted", Scripted({} if target == "post.txt" else worker_files))
    params = order(tmp_path)
    if target == "inputs":
        (tmp_path / "source.txt").write_bytes(b"\xff\xfe not text")
    else:
        class Binary(Scripted):
            def run(self, order_, cwd):
                (cwd / "post.txt").write_bytes(b"\xff\xfe")
                (cwd / "post.claims.json").write_text(worker_files["post.claims.json"])
                return super().run(order_, cwd)
        monkeypatch.setitem(workers.PROVIDERS, "scripted", Binary({}))
    workers.commission(params, ctx(tmp_path, "worker.commission"))
    out = workers.appraise({"order": "depot-note", "bound_claims": CONTRACT}, ctx(tmp_path, "worker.appraise"))
    assert out["verdict"] == "REJECTED" and any("not UTF-8 text" in f for f in out["findings"])


def test_a_malformed_signed_contract_is_rejected_and_never_used(tmp_path, monkeypatch):
    monkeypatch.setitem(workers.PROVIDERS, "scripted", Scripted(files(FAITHFUL)))
    workers.commission(order(tmp_path), ctx(tmp_path, "worker.commission"))
    out = workers.appraise({"order": "depot-note", "bound_claims": {"claims": "post.claims.json"}},
                           ctx(tmp_path, "worker.appraise"))
    assert out["verdict"] == "REJECTED" and "signed acceptance contract" in out["findings"][0]


def test_bound_claims_needs_inputs_with_distinct_names(tmp_path):
    params = order(tmp_path)
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "source.txt").write_text(SOURCE)
    for inputs in ([], [str(tmp_path / "source.txt"), str(tmp_path / "other" / "source.txt")]):
        with pytest.raises(workers.WorkerError, match="at least one input, each with its own file name"):
            workers.WorkOrder.from_params({**params, "inputs": inputs}, ctx(tmp_path, "worker.commission"))


# -- on a signed body mission ----------------------------------------------------------------------------------

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


def run_post(tmp_path, monkeypatch, worker_files, daleobanks: Path | None = None, **template):
    tmp_path.mkdir(parents=True, exist_ok=True)
    data = tmp_path / "data"
    daleobanks = daleobanks or stub_daleobanks(tmp_path / "daleobanks")
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data, daleobanks])
    (data / "source.txt").write_text(SOURCE)
    worker = Scripted(worker_files)
    monkeypatch.setitem(workers.PROVIDERS, "scripted", worker)
    spec = templates.daleobanks_post(daleobanks_root=str(daleobanks), source=str(data / "source.txt"),
                                     brief="Summarise the depot study.", order="depot-note", budget_usd=1.0,
                                     python=sys.executable, **template)
    next(s for s in spec["strategies"] if s["action_id"] == "draft-post")["params"]["provider"] = "scripted"
    drop(home, signed(key, body_id, "MISSION", spec))
    clock, states = Clock(), []
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(6):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
            if states[-1] in ("ACHIEVED", "BLOCKED", "EXHAUSTED", "FAILED"):
                break
        checks = {}
        for e in body.journal.replay("mission.observed"):
            checks[e.payload["check_id"]] = e.payload["passed"]
        publish_asked = any("daleobanks.publish" in json.dumps(e.payload) and "outside scope" in json.dumps(e.payload)
                            for e in body.journal.replay("mission."))
        outputs = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                   if isinstance(r.payload["result"].get("output"), dict)]
        context = body.engine._context(SimpleNamespace(mission_id="m:x"), BUILTINS["worker.appraise"][0])
        registry = body.engine.registry
    return SimpleNamespace(states=states, checks=checks, publish_asked=publish_asked, worker=worker,
                           appraisals=[o for o in outputs if "independence" in o],
                           verifies=[o for o in outputs if "daleobanks" in o], context=context, registry=registry)


def test_a_worker_drafted_post_that_drops_a_hedge_never_reaches_the_publish_request(tmp_path, monkeypatch):
    hedge = [("A two-depot study found the routing method cuts delays by 12%.", STUDY), FAITHFUL[1]]
    run = run_post(tmp_path, monkeypatch, files(hedge))
    assert run.checks["draft_verified"] is True              # DALEOBANKS's figure-and-content check passes it...
    assert run.checks["draft_appraised"] is False            # ...the Task Fabric's evaluator, asking the Mind, does not
    assert run.publish_asked is False and run.states[-1] == "BLOCKED"
    assert run.worker.calls == 1                              # no automatic re-drafting spend
    assert "certainty" in {d["class"] for d in run.appraisals[-1]["truth_preservation"]["distortions"]}


def test_a_faithful_worker_drafted_post_waits_for_the_founder_and_nothing_is_posted(tmp_path, monkeypatch):
    run = run_post(tmp_path, monkeypatch, files(FAITHFUL))
    assert run.checks["draft_verified"] is True and run.checks["draft_appraised"] is True
    assert run.publish_asked is True and run.states[-1] == "WAITING"   # external contact: a founder decision
    assert run.checks.get("publish_outcome_known") is False
    assert all(_valid_receipt(r) for r in run.appraisals[-1]["cognition_receipts"].values())


def test_the_evaluator_gets_the_bodys_registry_and_no_ledger(tmp_path, monkeypatch):
    """No ledger it can write (#185). Joined with #192 (H.G11) the evaluator reads one: it binds a retained work
    order to its canonical commission receipt, through a handle that offers only ``ledger.by_type``."""
    from greg.ventures import LedgerReader
    run = run_post(tmp_path, monkeypatch, files(FAITHFUL))
    assert run.context.capability_registry is run.registry and isinstance(run.context.journal, LedgerReader)
    assert not hasattr(run.context.journal, "record") and not hasattr(run.context.journal.ledger, "append")


def test_without_bound_claims_the_post_mission_is_the_figure_only_floor():
    spec = templates.daleobanks_post(daleobanks_root="/tmp", source="/tmp/source.txt", brief="b", order="o",
                                     bound_claims=False)
    assert "worker.appraise" not in spec["light_cone"]["capabilities"]
    assert next(s for s in spec["strategies"] if s["action_id"] == "request-publish")["requires"] == ["draft_verified"]
    spec = templates.daleobanks_post(daleobanks_root="/tmp", source="/tmp/source.txt", brief="b", order="o")
    publish = next(s for s in spec["strategies"] if s["action_id"] == "request-publish")
    draft = next(s for s in spec["strategies"] if s["action_id"] == "draft-post")
    appraised = next(c for c in spec["success_checks"] if c["check_id"] == "draft_appraised")
    assert publish["requires"] == ["draft_verified", "draft_appraised"]
    assert appraised["sensor"]["params"]["bound_claims"] == draft["params"]["acceptance"]["bound_claims"]
    assert "daleobanks.publish" not in spec["light_cone"]["capabilities"]


@pytest.mark.skipif(not os.environ.get("GREG_TEST_DALEOBANKS"), reason="set GREG_TEST_DALEOBANKS to a DALEOBANKS checkout")
def test_on_the_real_daleobanks_its_own_checks_pass_a_distorted_draft_and_the_mind_holds_it_back(tmp_path, monkeypatch):
    root = Path(os.environ["GREG_TEST_DALEOBANKS"]).resolve()
    negation = [FAITHFUL[0], ("It lowered fuel costs.", FUEL)]
    run = run_post(tmp_path / "bad", monkeypatch, files(negation), daleobanks=root)
    own = run.verifies[-1]["daleobanks"]
    assert own["ethics"]["approved"] and not own["critic"]["blocking_issues"] and run.checks["draft_verified"]
    assert run.checks["draft_appraised"] is False and run.publish_asked is False
    good = run_post(tmp_path / "good", monkeypatch, files(FAITHFUL), daleobanks=root)
    assert good.checks["draft_appraised"] is True and good.publish_asked is True


class LinkedClaims(Scripted):
    """Test double: writes the deliverable, and makes its claims file a symlink to a host file it names."""

    def __init__(self, files: dict, target: Path):
        super().__init__(files)
        self.target = target

    def run(self, order, cwd):
        report = super().run(order, cwd)
        (cwd / "post.claims.json").unlink(missing_ok=True)
        os.symlink(self.target, cwd / "post.claims.json")
        return report


@pytest.mark.parametrize("target", ["host-file", "/proc/self/mem"])
def test_a_claims_file_that_leaves_the_clone_is_never_read(tmp_path, monkeypatch, target):
    """#184 reads a worker-written deliverable only inside the fresh clone. Joined with #185, the claims file the Mind
    checks is a second worker-written file, held to the same rule: a symlink out of the clone is refused unread,
    and a host file that cannot be read rejects instead of raising."""
    host = tmp_path / "outside" / "claims.json"
    host.parent.mkdir()
    host.write_text(files(FAITHFUL)["post.claims.json"])          # a host file that parses as faithful claims
    link = host if target == "host-file" else Path(target)
    monkeypatch.setitem(workers.PROVIDERS, "scripted", LinkedClaims(files(FAITHFUL), link))
    workers.commission(order(tmp_path), ctx(tmp_path, "worker.commission"))
    out = workers.appraise({"order": "depot-note", "bound_claims": CONTRACT}, ctx(tmp_path, "worker.appraise"))
    assert out["verdict"] == "REJECTED"
    assert any("leaves the private workspace" in f for f in out["findings"]), out["findings"]
    assert not out.get("cognition_receipts")                      # nothing the host file says reached the Mind
