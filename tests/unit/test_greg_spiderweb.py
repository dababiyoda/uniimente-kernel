"""Spider-Web compounding: routing learned from receipts, independent appraisal,
the capability rule, the real repository guardian and the ledger-derived VEPMC."""
from dataclasses import replace
import json
import subprocess

import pytest

from greg import metrics, routing, templates
from greg.body import Body
from greg.capabilities import BUILTINS, CapabilityError, CapabilityManifest, CapabilityRegistry
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy
from tests.unit.test_greg_missions import events, run, submit

PIN = "4999acff1a69502c05af455fbccfca380cad18ee"


def test_spider_web_rule_rejects_capabilities_that_strengthen_nothing():
    registry = CapabilityRegistry()
    manifest, adapter = BUILTINS["fs.read"]
    with pytest.raises(CapabilityError, match="Spider-Web rule"):
        registry.register(replace(manifest, capability_id="orphan.cap", strengthens=()), adapter, state="ATTACHED")
    with pytest.raises(CapabilityError, match="unknown super-nodes"):
        registry.register(replace(manifest, capability_id="vanity.cap", strengthens=("coolness",)), adapter,
                          state="ATTACHED")
    assert all(m.strengthens for m, _ in BUILTINS.values())


def test_routing_learns_from_one_missions_failure_for_the_next_mission(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    calls = []

    def flaky(params, ctx):
        calls.append("flaky")
        raise CapabilityError("upstream service returned 500")

    flaky_manifest = CapabilityManifest(capability_id="demo.flaky_write", version="1.0.0", provider="test",
                                        function="note.write", description="unreliable writer", route="api",
                                        consequence_class="internal_write", inputs={"x": "str"},
                                        outputs={"ok": "bool"}, target_prefix="workspace:",
                                        strengthens=("settlement",))
    clock = Clock()
    for n in (1, 2):
        mid = f"m:route-learning-{n}"
        drop(home, signed(key, body_id, "MISSION", mission(
            mid, checks=[note_check("n", workspace(home, mid) / "n.txt", "ok")],
            strategies=[{"action_id": "cheap-flaky", "capability": "demo.flaky_write", "params": {},
                         "target": "workspace:n.txt", "advances": ["n"], "rationale": "cheap"},
                        write_strategy("reliable", "n.txt", "ok", ["n"], cost_usd=0.1)],  # 0.5-0.1=0.4 > 1/3 after one failure
            capabilities=["fs.read", "fs.write", "demo.flaky_write"], budget=1.0, priority=10 - n)))
    with Body(home, clock=clock) as body:
        body.registry.register(flaky_manifest, flaky, state="ATTACHED")
        for _ in range(10):
            body.tick()
            clock.advance(1)
        actions = [e.payload for e in body.journal.replay("mission.action")]
        knowledge = {r["capability"]: r for r in routing.routing_knowledge(body.journal)}
    first = [a["action_id"] for a in actions if a["mission_id"] == "m:route-learning-1"]
    second = [a["action_id"] for a in actions if a["mission_id"] == "m:route-learning-2"]
    assert first[0] == "cheap-flaky" and "reliable" in first          # no history: cheapest first
    assert second[0] == "reliable" and "cheap-flaky" not in second     # history: routed around failure
    assert knowledge["demo.flaky_write"]["failed"] == 1 and knowledge["demo.flaky_write"]["reliability"] < 0.5
    decision = next(a["routing"] for a in actions if a["mission_id"] == "m:route-learning-2")
    assert decision["chosen"] == "reliable" and decision["alternatives"][0]["action_id"] == "cheap-flaky"
    assert calls == ["flaky"]


def test_independent_appraiser_verifies_honest_closure_and_refutes_changed_world(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    note = workspace(home, "m:appraised") / "n.txt"
    submit(home, key, body_id, "MISSION", mission("m:appraised", checks=[note_check("n", note, "true")],
                                                  strategies=[write_strategy("w", "n.txt", "true fact", ["n"])],
                                                  capabilities=["fs.read", "fs.write"]))
    run(home, Clock(), ticks=4)
    appraisal = events(home, "mission.appraised")[0]
    assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
    for check in ("founder_signature_verified", "checks_rederived_from_receipts", "world_reobserved",
                  "exactly_once", "arrived_via_inbox"):
        assert appraisal["checks"][check], check
    note.write_text("the world changed")
    with Body(home) as body:
        again = body.appraise("m:appraised")
    assert again["verdict"] == "REFUTED" and not again["checks"]["world_reobserved"]


def test_appraiser_refutes_a_false_closure_claim(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    note = workspace(home, "m:false-claim") / "n.txt"
    submit(home, key, body_id, "MISSION", mission("m:false-claim", checks=[note_check("n", note, "done")],
                                                  strategies=[], capabilities=["fs.read"]))
    run(home, Clock(), ticks=2)  # engine observes failure; nothing is achieved
    with Body(home) as body:
        body.journal.record("mission.achieved", {"mission_id": "m:false-claim", "evidence": [],
                                                 "note": "hostile: a worker claims closure"}, key="forged")
        verdict = body.appraise("m:false-claim")
    assert verdict["verdict"] == "REFUTED"
    assert any("receipt bytes do not satisfy" in f or "no retained receipt" in f for f in verdict["findings"])


def _repo(tmp_path, role, pin, version="0.1.2"):
    path = tmp_path / "repos" / role
    path.mkdir(parents=True)
    dep = f"uniimente-kernel-boundaries @ https://github.com/dababiyoda/uniimente-kernel/archive/{pin}.tar.gz"
    project = {"kernel": f'[project]\nname="k"\nversion="{version}"\n'}.get(
        role, f'[project]\nname="o"\nversion="1"\ndependencies=[{json.dumps(dep)}]\n')
    (path / "pyproject.toml").write_text(project)
    if role != "kernel":
        (path / "requirements.txt").write_text(dep + "\n")
    git = lambda *a: subprocess.check_output(["git", "-C", str(path), *a], stderr=subprocess.DEVNULL).decode().strip()
    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "-c", "commit.gpgsign=false",
        "commit", "-qm", "state")
    git("update-ref", "refs/remotes/origin/main", git("rev-parse", "HEAD"))
    return path, git


def test_repository_guardian_holds_then_escalates_real_git_drift_once(tmp_path):
    repos = {role: _repo(tmp_path, role, PIN) for role in ("kernel", "dale", "wmi")}
    home, key, body_id, data = make_body(tmp_path, read_roots=[tmp_path / "repos"])
    spec = templates.repo_guardian(repositories={r: str(p) for r, (p, _) in repos.items()}, expected_pin=PIN,
                                   expected_version="0.1.2", cadence_seconds=60)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    missions, requests = run(home, clock, ticks=3)
    assert missions["m:repo-guardian"].status == "ACTIVE" and not requests  # consistent: holding
    dale, git = repos["dale"]
    (dale / "requirements.txt").write_text(
        "uniimente-kernel-boundaries @ https://github.com/dababiyoda/uniimente-kernel/archive/" + "b" * 40 + ".tar.gz\n")
    git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "-c", "commit.gpgsign=false",
        "commit", "-qam", "drift")
    git("update-ref", "refs/remotes/origin/main", git("rev-parse", "HEAD"))
    clock.advance(61)
    missions, requests = run(home, clock, ticks=5)
    assert [r["kind"] for r in requests] == ["NO_STRATEGY"]  # one evidence-backed decision, no spam
    failing = [o for o in events(home, "mission.observed") if not o["passed"]]
    assert failing and failing[-1]["check_id"] == "organs-consistent"
    assert not [a for a in events(home, "mission.action")]  # the guardian never touches repositories


def test_vepmc_is_derived_from_evidence_and_needs_founder_and_mac(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    note = workspace(home, "m:vepmc-probe") / "n.txt"
    submit(home, key, body_id, "MISSION", mission("m:vepmc-probe", checks=[note_check("n", note, "x")],
                                                  strategies=[write_strategy("w", "n.txt", "x", ["n"])],
                                                  capabilities=["fs.read", "fs.write"]))
    run(home, Clock(), ticks=4)
    with Body(home) as body:
        result = metrics.vepmc(body.journal)
    row = result["missions"][0]
    assert result["VEPMC"] == 0 and row["founder_signed"] and row["real_capability"] and row["appraised_verified"]
    # Direct ticks are not a hosted body, no interruption, no approval, no founder acceptance, no Mac.
    assert {"persistent_runtime", "interruption_survived", "approval_boundary", "founder_accepted"} <= set(row["missing"])


def test_appraiser_refutation_of_the_effect_lowers_routing_but_foreign_faults_do_not(tmp_path):
    """Proof -> Routing: a closure the independent appraiser refutes because the
    world does not hold teaches every future mission to distrust that capability."""
    home, key, body_id, data = make_body(tmp_path)
    note = workspace(home, "m:proof-routes") / "n.txt"
    submit(home, key, body_id, "MISSION", mission("m:proof-routes", checks=[note_check("n", note, "true")],
                                                  strategies=[write_strategy("w", "n.txt", "true", ["n"])],
                                                  capabilities=["fs.read", "fs.write"]))
    run(home, Clock(), ticks=4)
    with Body(home) as body:
        before = {r["capability"]: r for r in routing.routing_knowledge(body.journal)}["fs.write"]
        verified = body.journal.replay("mission.appraised")[0].payload
        # A refutation that is not the writer's fault (founder signature) leaves routing alone.
        foreign = {**verified, "verdict": "REFUTED", "head": "foreign",
                   "checks": {**verified["checks"], "founder_signature_verified": False}}
        body.journal.record("mission.appraised", foreign, key=["m:proof-routes", "foreign"])
        neutral = {r["capability"]: r for r in routing.routing_knowledge(body.journal)}["fs.write"]
        note.write_text("the world changed")
        refuted = body.appraise("m:proof-routes")
        body.journal.record("mission.appraised", refuted, key=["m:proof-routes", "refuted"])
        after = {r["capability"]: r for r in routing.routing_knowledge(body.journal)}["fs.write"]
    assert before["verified"] == 1 and before["refuted"] == 0
    assert neutral["refuted"] == 0 and neutral["reliability"] == before["reliability"]
    assert refuted["verdict"] == "REFUTED" and not refuted["checks"]["world_reobserved"]
    assert after["refuted"] == 1 and after["reliability"] < before["reliability"]


def test_strategy_tribunal_super_nodes_translate_into_the_capability_rule():
    from evolution import spider_web
    from greg.capabilities import STRATEGY_SUPER_NODES, SUPER_NODES
    assert set(spider_web.SUPER_NODES) == set(STRATEGY_SUPER_NODES)
    assert set(STRATEGY_SUPER_NODES.values()) <= set(SUPER_NODES)


VULNERABLE_RESUME = '''
def require_hash(name, value):
    return value


class StandingCognitionRuntime:
    def resume(self, *, actor, authorization_hash):
        return require_hash("authorization_hash", authorization_hash)
'''
FIXED_RESUME = '''
class StandingCognitionRuntime:
    def resume(self, *, actor, gate=None, grant=None):
        return gate.run(self.resume_proposal(actor), standing_grant=grant)
'''


def _integration_repos(tmp_path, runtime_source):
    extra = {"kernel": {"egregore/runtime.py": runtime_source, "policy/consequence_gate.py": "GATE = 1\n"},
             "dale": {"services/reflection.py": "def learn(outcome):\n    return outcome['follower_delta']\n",
                      "services/generator.py": "def draft():\n    return 'text'\n"},
             "wmi": {"src/services/bridge_security.py": "KNOWN = frozenset({'kernel'})\n"}}
    repos = {}
    for role in ("kernel", "dale", "wmi"):
        path, git = _repo(tmp_path, role, PIN)
        for name, text in extra[role].items():
            (path / name).parent.mkdir(parents=True, exist_ok=True)
            (path / name).write_text(text)
        git("add", ".")
        git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "-qm", "integration sources")
        git("update-ref", "refs/remotes/origin/main", git("rev-parse", "HEAD"))
        repos[role] = (path, git)
    return repos


def test_integration_watch_escalates_a_real_authority_defect_once_then_holds_after_the_fix(tmp_path):
    """The mission #112 ran by hand, on the signed body: find the stop-bypass in source, tell
    Alfonso once with exact evidence, and hold again when the fix lands."""
    repos = _integration_repos(tmp_path, VULNERABLE_RESUME)
    home, key, body_id, data = make_body(tmp_path, read_roots=[tmp_path / "repos"])
    drop(home, signed(key, body_id, "MISSION", templates.integration_watch(
        repositories={r: str(p) for r, (p, _) in repos.items()}, expected_pin=PIN, expected_version="0.1.2",
        cadence_seconds=60)))
    clock = Clock()
    missions, requests = run(home, clock, ticks=4)
    assert [r["kind"] for r in requests] == ["NO_STRATEGY"]
    failing = [o for o in events(home, "mission.observed") if not o["passed"]]
    assert {o["check_id"] for o in failing} == {"no-authority-blockers"}
    with Body(home) as body:
        receipt = next(e.payload for e in body.journal.replay("mission.observed")
                       if e.payload["check_id"] == "no-authority-blockers")
    assert "resume-authority" in json.dumps(receipt)  # the source evidence travels with the decision
    kernel, git = repos["kernel"]
    (kernel / "egregore/runtime.py").write_text(FIXED_RESUME)
    git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "-c", "commit.gpgsign=false",
        "commit", "-qam", "resume consumes a Gate grant")
    git("update-ref", "refs/remotes/origin/main", git("rev-parse", "HEAD"))
    clock.advance(61)
    missions, requests = run(home, clock, ticks=4)
    latest = {}
    for o in events(home, "mission.observed"):
        latest[o["check_id"]] = o["passed"]
    assert latest == {"pins-consistent": True, "no-authority-blockers": True}
    assert requests == [] and missions["m:integration-watch"].blocker is None  # healed: holding again
    withdrawn = events(home, "decision.withdrawn")
    assert len(withdrawn) == 1 and "without any GREG action" in withdrawn[0]["why"]
    assert len(events(home, "decision.requested")) == 1
    # The defect returns: a fresh escalation, never deduplicated into silence by the old withdrawn one.
    (kernel / "egregore/runtime.py").write_text(VULNERABLE_RESUME)
    git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "-c", "commit.gpgsign=false",
        "commit", "-qam", "regression")
    git("update-ref", "refs/remotes/origin/main", git("rev-parse", "HEAD"))
    clock.advance(61)
    missions, requests = run(home, clock, ticks=4)
    assert [r["kind"] for r in requests] == ["NO_STRATEGY"] and requests[0]["request_id"] != withdrawn[0]["request_id"]
    with Body(home) as body:
        with pytest.raises(Exception, match="withdrawn"):
            body.engine.answer({"request_id": withdrawn[0]["request_id"], "answer": "approve"}, "sha256:" + "0" * 64)
    assert not events(home, "mission.action")  # read-only throughout: GREG never touched a repository
