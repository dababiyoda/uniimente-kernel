"""The Founder's First Mission on a real body: signed, bound, delivered, appraised, crash-safe.

A per-test Ed25519 key stands in for the founder; nothing here claims Alfonso's authentication.
"""
import json
import shutil
from pathlib import Path

from greg.body import Body
from greg.templates import first_mission
from tests.greg_fixtures import drop, make_body, signed

REPO = Path(__file__).resolve().parents[2]


def kernel_copy(tmp: Path) -> Path:
    """The two sources the mission reads, copied so the test owns their bytes."""
    root = tmp / "data" / "kernel"
    for rel in ("greg/path.json", "foundry/completion.yaml"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / rel, root / rel)
    return root


def setup(tmp_path, *, attach=True, budget=8):
    home, key, body_id, data = make_body(tmp_path)
    root = kernel_copy(tmp_path)
    spec = first_mission(kernel_root=str(root), effort_budget=budget, run="test")
    if attach:
        drop(home, signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.dp_knapsack"}), "a.json")
    drop(home, signed(key, body_id, "MISSION", spec), "m.json")
    return home, key, body_id, root, spec


def run_until_settled(home, limit=12):
    with Body(home) as body:
        body.boot()
        for _ in range(limit):
            out = body.tick()
            states = [m["state"] for m in out["missions"]]
            if any(s in ("ACHIEVED", "BLOCKED") for s in states):
                return out, body
        return out, body


def actions(home, mission_id):
    with Body(home) as body:
        return [e.payload for e in body.journal.replay("mission.action") if e.payload["mission_id"] == mission_id]


def test_first_mission_runs_end_to_end_and_is_independently_verified(tmp_path):
    home, _, _, root, spec = setup(tmp_path)
    out, _ = run_until_settled(home)
    assert out["missions"][0]["state"] == "ACHIEVED", out
    done = [a for a in actions(home, spec["mission_id"]) if a["status"] == "DONE"]
    assert [a["action_id"] for a in done] == ["survey", "select", "compose", "dossier"] or \
        [a["action_id"] for a in done] == ["survey", "compose", "select", "dossier"]
    assert all(a.get("bindings") for a in done if a["action_id"] != "survey"), "typed edges, no manual relay"
    delivered = sorted((home / "deliveries" / "first-mission").glob("*.json"))
    assert len(delivered) == 1
    doc = json.loads(delivered[0].read_text())
    assert doc["authority_created"] is False and doc["objective"]["node"]
    assert doc["selection"]["weight"] <= 8 and doc["next_work_order"]["acceptance"]["must_not"]
    assert all(d["why_founder"] for d in doc["founder_decisions"])   # founder-only items are routed, not worked
    with Body(home) as body:
        appraised = [e.payload for e in body.journal.replay("mission.appraised")
                     if e.payload["mission_id"] == spec["mission_id"]][-1]
        assert appraised["verdict"] == "VERIFIED", appraised
        assert not body.journal.replay("routing.outcome"), "pipeline steps are not scored as ineffective"


def test_crash_after_survey_resumes_without_repeating_a_completed_step(tmp_path):
    home, _, _, _, spec = setup(tmp_path)
    with Body(home) as body:           # the first tick runs exactly one step, then the process "dies"
        body.boot()
        body.tick()
    first = [a for a in actions(home, spec["mission_id"]) if a["status"] == "DONE"]
    assert [a["action_id"] for a in first] == ["survey"]
    out, _ = run_until_settled(home)    # a new process: reboot from the journal
    assert out["missions"][0]["state"] == "ACHIEVED"
    done = [a["action_id"] for a in actions(home, spec["mission_id"]) if a["status"] == "DONE"]
    assert done.count("survey") == 1 and done.count("dossier") == 1, done
    assert len(list((home / "deliveries" / "first-mission").glob("*.json"))) == 1
    run_until_settled(home, limit=2)    # restarting a settled body adds no consequence
    assert [a["action_id"] for a in actions(home, spec["mission_id"]) if a["status"] == "DONE"] == done


def test_unattached_selection_engine_stops_for_the_founder_instead_of_running(tmp_path):
    home, key, body_id, _, spec = setup(tmp_path, attach=False)
    out, _ = run_until_settled(home)
    assert out["missions"][0]["state"] != "ACHIEVED"
    assert "select" not in [a["action_id"] for a in actions(home, spec["mission_id"]) if a["status"] == "DONE"]
    assert not list((home / "deliveries").glob("first-mission/*.json"))


def test_tampered_dossier_is_refuted_by_the_independent_sensor(tmp_path):
    from greg.capabilities import BUILTINS, InvocationContext
    home, _, _, root, spec = setup(tmp_path)
    run_until_settled(home)
    path = next((home / "deliveries" / "first-mission").glob("*.json"))
    manifest, adapter = BUILTINS["institution.appraise"]
    ctx = InvocationContext(workspace=tmp_path / "w", read_roots=(tmp_path / "data",), secrets=None,
                            manifest=manifest, deliver_root=home / "deliveries", mission_id=spec["mission_id"])
    assert adapter({"kernel_root": str(root)}, ctx)["verdict"] == "VERIFIED"
    doc = json.loads(path.read_text())
    doc["selection"]["value"] += 1                        # an inflated claim
    path.write_text(json.dumps(doc))
    refuted = adapter({"kernel_root": str(root)}, ctx)
    assert refuted["verdict"] == "REFUTED" and any("value" in f for f in refuted["findings"])
    doc["selection"]["value"] -= 1
    doc["selection"]["indexes"] = doc["selection"]["greedy_indexes"][:1]   # a feasible but suboptimal pick
    doc["selection"]["value"] = sum(c["value"] for i, c in enumerate(doc["candidates"]) if i in doc["selection"]["indexes"])
    path.write_text(json.dumps(doc))
    assert adapter({"kernel_root": str(root)}, ctx)["verdict"] == "REFUTED"
    (root / "greg" / "path.json").write_text((root / "greg" / "path.json").read_text().replace("CURRENTLY_BUILDABLE", "PROPOSED", 1))
    assert any("sources changed" in f for f in adapter({"kernel_root": str(root)}, ctx)["findings"])


def test_kernel_root_outside_read_roots_is_refused(tmp_path):
    from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
    import pytest
    manifest, adapter = BUILTINS["institution.survey"]
    ctx = InvocationContext(workspace=tmp_path, read_roots=(tmp_path / "elsewhere",), secrets=None, manifest=manifest)
    with pytest.raises(CapabilityError, match="read roots"):
        adapter({"kernel_root": str(REPO), "effort_budget": 8}, ctx)
    ctx = InvocationContext(workspace=tmp_path, read_roots=(REPO,), secrets=None, manifest=manifest)
    for bad in (0, 201, True, "8"):
        with pytest.raises(CapabilityError, match="effort_budget"):
            adapter({"kernel_root": str(REPO), "effort_budget": bad}, ctx)


def test_dossier_path_cannot_be_steered_by_parameters(tmp_path):
    import pytest
    from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
    root = kernel_copy(tmp_path)
    manifest, adapter = BUILTINS["institution.appraise"]
    for bad in ("../../etc/passwd", "m:../x", "m:A", "", None):
        ctx = InvocationContext(workspace=tmp_path, read_roots=(tmp_path / "data",), secrets=None, manifest=manifest,
                                deliver_root=tmp_path / "out", mission_id=bad or "")
        with pytest.raises(CapabilityError, match="mission id"):
            adapter({"kernel_root": str(root), **({"mission_id": bad} if bad else {})}, ctx)
