"""License qualification bound to GREG's actual use: drafts D-LIC-1 and P4c (directive of 2026-10-23).

A license permits a use, not a package. These tests fix what the drafts must do before the founder adopts them:
judge each declared term against the route's real use (an unmodified, network-isolated, never-redistributed
separate process under a read-only scope), bind the verdict to the exact assessed facts, requalify before a run
when facts or use change, refuse a bare founder attach past an unresolved hold, and leave compatible open-source
use (GPL coreutils, AGPL run locally) unobstructed. The active policies stay P0; every draft is exercised by
passing or patching the policy explicitly. In-process Body with a test clock (SANDBOX); per-test founder key.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from greg import genesis as genesis_mod, licensing
from tests.greg_fixtures import Clock, make_body, mission
from tests.unit.test_greg_missions import events, run, submit

USE = licensing.GREG_USE
REPO = Path(__file__).resolve().parents[2]
PATCH = REPO / "docs/open-source/binary-license-policy-2026-10-22/d-lic-1-body-hook.patch"


def assessment(*terms):
    """A DEP-5-shaped assessment with the given (id, class) terms."""
    parts = [{"distribution": "pkg (dpkg)", "expression": " AND ".join(t[0] for t in terms), "basis": "test",
              "class": licensing._worst([t[1] for t in terms]),
              "terms": [{"id": i, "class": c} for i, c in terms]}]
    held = bool(licensing._held_terms(parts[0]["terms"]))
    return {"class": parts[0]["class"], "held": held, "auto_attach": not held, "parts": parts,
            "reason": parts[0]["expression"]}


class Manifest:
    capability_id = "acquired.hash.sha256.tool"
    provider = "installed:/usr/bin/tool"

    def __init__(self, main, companions=None, sha="a" * 64):
        self.provenance = {"binary": "/usr/bin/tool", "binary_sha256": sha, "version": "tool 1.0",
                           "license_assessment": main,
                           "companions": {n: {"binary": f"/usr/bin/{n}", "binary_sha256": "b" * 64,
                                              "license_assessment": a} for n, a in (companions or {}).items()}}


GPL = assessment(("GPL-3+", licensing.STRONG_COPYLEFT))
AGPL = assessment(("AGPL-3.0", licensing.NETWORK_COPYLEFT))
UNREAD = assessment(("public-domain-ish", licensing.UNKNOWN))
SSPL = assessment(("SSPL-1.0", licensing.NOT_OPEN))


def clearance_for(manifest, **over):
    q = licensing.capability_qualification(manifest)
    return {"assessment_digest": q["assessment_digest"], "use": q["use"], "basis": "read the license text: it is MIT",
            "obligations_accepted": q["obligations"], **over}


# -- the verdict judges the use, not the license's reputation --------------------------------------------------

@pytest.mark.parametrize("cls, use, verdict", [
    (licensing.PERMISSIVE, USE, licensing.COMPATIBLE),
    (licensing.WEAK_COPYLEFT, USE, licensing.COMPATIBLE),
    (licensing.STRONG_COPYLEFT, USE, licensing.COMPATIBLE),                      # GPL is not prohibited
    (licensing.STRONG_COPYLEFT, {**USE, "redistributed": True}, licensing.UNCERTAIN),
    (licensing.STRONG_COPYLEFT, {**USE, "interaction": "linked"}, licensing.UNCERTAIN),
    (licensing.NETWORK_COPYLEFT, USE, licensing.COMPATIBLE),                     # nor is AGPL, run locally
    (licensing.NETWORK_COPYLEFT, {**USE, "network": "serves_users"}, licensing.UNCERTAIN),
    (licensing.NETWORK_COPYLEFT, {**USE, "modified": True}, licensing.UNCERTAIN),
    (licensing.NOT_OPEN, USE, licensing.INCOMPATIBLE),
    (licensing.UNKNOWN, USE, licensing.UNCERTAIN),          # no network and no redistribution prove nothing
])
def test_each_term_is_judged_against_the_routes_real_use(cls, use, verdict):
    assert licensing.qualify_use([assessment(("X", cls))], use, {})["verdict"] == verdict


def test_conflicting_terms_take_the_worst_verdict_and_name_it():
    q = licensing.qualify_use([assessment(("MIT", licensing.PERMISSIVE), ("SSPL-1.0", licensing.NOT_OPEN))], USE, {})
    assert q["verdict"] == licensing.INCOMPATIBLE and "SSPL-1.0" in q["reason"]
    q = licensing.capability_qualification(Manifest(GPL, {"helper": AGPL}), {**USE, "network": "serves_users"})
    assert q["verdict"] == licensing.UNCERTAIN and "AGPL-3.0" in q["reason"]     # a companion counts


def test_an_unreadable_license_is_uncertain_never_compatible():
    assert licensing.qualify_use([None], USE, {})["verdict"] == licensing.UNCERTAIN
    assert licensing.capability_qualification(Manifest(None))["verdict"] == licensing.UNCERTAIN


def test_the_digest_binds_the_binary_version_companions_and_declaration_but_not_unrelated_fields():
    base = licensing.capability_qualification(Manifest(GPL))["assessment_digest"]
    assert licensing.capability_qualification(Manifest(GPL, sha="c" * 64))["assessment_digest"] != base   # altered
    corrected = assessment(("GPL-3+", licensing.STRONG_COPYLEFT), ("SSPL-1.0", licensing.NOT_OPEN))
    assert licensing.capability_qualification(Manifest(corrected))["assessment_digest"] != base   # declaration
    assert licensing.capability_qualification(Manifest(GPL, {"helper": GPL}))["assessment_digest"] != base
    reworded = {**GPL, "reason": "same facts, different prose"}
    assert licensing.capability_qualification(Manifest(reworded))["assessment_digest"] == base


# -- P4c: automatic attach and execution -------------------------------------------------------------------

def test_p4c_holds_what_is_not_compatible_and_says_how_to_lift_it_while_p0_is_unchanged():
    for main, p0, p4c in ((GPL, True, True), (AGPL, False, True), (UNREAD, True, False), (SSPL, False, False),
                          (None, True, False)):
        assert licensing.attach_check(Manifest(main), "P0")[0] is p0
        ok, why = licensing.attach_check(Manifest(main), "P4c")
        assert ok is p4c and (ok or "founder clearance" in why)
    assert licensing.attach_check(Manifest(GPL, {"pdfimages": UNREAD}), "P4c")[0] is False   # companion holds


def test_requalification_refuses_a_run_when_facts_or_use_changed():
    m = Manifest(GPL)
    m.provenance["use_qualification"] = licensing.capability_qualification(m)
    assert licensing.requalify(m, [GPL], policy="P4c") == (True, "")
    ok, why = licensing.requalify(m, [AGPL], policy="P4c")                      # the OS package changed license
    assert not ok and "license facts changed" in why
    for changed in ({"network": "serves_users"}, {"redistributed": True}, {"modified": True}, {"scope": "write"}):
        ok, why = licensing.requalify(m, [GPL], {**USE, **changed}, policy="P4c")
        assert not ok and "use context changed" in why
    del m.provenance["use_qualification"]
    assert licensing.requalify(m, [GPL], policy="P4c")[0] is False              # never qualified: not run
    assert licensing.requalify(m, [AGPL], policy="P0") == (True, "")            # P0 does not requalify


def sha_check(path, content):
    return {"check_id": "hashed", "description": "digest known",
            "sensor": {"function": "hash.sha256", "params": {"path": str(path)}, "target": f"fs:{path.name}"},
            "predicate": {"op": "equals", "field": "sha256", "value": hashlib.sha256(content).hexdigest()}}


SCOPE = dict(capabilities=["fs.read", "acquired.hash.sha256.*"], ceiling="read_only", auto_attach=True)
needs_sha = pytest.mark.skipif(genesis_mod.installed_binary("sha256sum") is None,
                               reason="no sha256sum on this body; genesis would correctly escalate")


def _route(tmp_path, monkeypatch, declared):
    monkeypatch.setattr(licensing, "ACTIVE_BINARY_POLICY", "P4c")
    state = {"declared": declared}
    monkeypatch.setattr(licensing, "system_binary", lambda binary: state["declared"])
    home, key, body_id, data = make_body(tmp_path)
    f = data / "evidence.bin"
    f.write_bytes(b"founder evidence")
    submit(home, key, body_id, "MISSION", mission("m:licensed", checks=[sha_check(f, b"founder evidence")], strategies=[],
                                                  **SCOPE))
    clock = Clock()
    missions, _ = run(home, clock, ticks=4)
    return home, key, body_id, data, clock, missions, state


@needs_sha
def test_p4c_leaves_compatible_gpl_use_unobstructed_on_the_mission_path(tmp_path, monkeypatch):
    home, *_, missions, _ = _route(tmp_path, monkeypatch, GPL)
    assert missions["m:licensed"].status == "ACHIEVED"
    [attached] = [e for e in events(home, "capability.state") if e["state"] == "ATTACHED"]
    assert attached["capability_id"].startswith("acquired.hash.sha256.")


@needs_sha
def test_p4c_holds_an_unclassified_binary_at_the_mission_attach_route(tmp_path, monkeypatch):
    home, *_, missions, _ = _route(tmp_path, monkeypatch, UNREAD)
    assert missions["m:licensed"].status != "ACHIEVED"
    assert not [e for e in events(home, "capability.state") if e["state"] == "ATTACHED"
                and e["capability_id"].startswith("acquired.")]
    assert any("founder clearance" in e["why"] for e in events(home, "deficit.awaiting_attach"))


@needs_sha
def test_p4c_stops_an_attached_binary_whose_license_changed_before_the_next_run(tmp_path, monkeypatch):
    home, key, body_id, data, clock, missions, state = _route(tmp_path, monkeypatch, GPL)
    assert missions["m:licensed"].status == "ACHIEVED"
    state["declared"] = SSPL                                    # an OS upgrade relicensed the package
    g = data / "second.bin"
    g.write_bytes(b"second")
    submit(home, key, body_id, "MISSION", mission("m:relicensed", checks=[sha_check(g, b"second")], strategies=[], **SCOPE))
    missions, _ = run(home, clock, ticks=4)
    assert missions["m:relicensed"].status != "ACHIEVED"


def test_the_dependency_attach_route_obeys_the_same_policy(monkeypatch):
    class Mission:
        spec = {"auto_attach": {"max_consequence_class": "read_only"}}

        class cone:
            @staticmethod
            def _capability_inside(_):
                return True

    class Stub:
        _form_only = None
    m = Manifest(UNREAD)
    m.consequence_class = "read_only"
    monkeypatch.setattr(licensing, "ACTIVE_BINARY_POLICY", "P4c")
    assert genesis_mod.Genesis._attach_dependency(Stub(), Mission(), m, "composed.x", None) is False


# -- D-LIC-1: the founder's own attach ---------------------------------------------------------------------

def test_p0_founder_attach_is_inert_and_a_compatible_capability_needs_no_clearance():
    assert licensing.founder_attach_check(Manifest(SSPL), {}) == (True, "", None)            # active P0
    assert licensing.founder_attach_check(Manifest(GPL), {}, "D-LIC-1", "P4c") == (True, "", None)


def test_d_lic_1_refuses_a_bare_attach_past_an_unresolved_hold():
    ok, why, record = licensing.founder_attach_check(Manifest(UNREAD), {}, "D-LIC-1", "P4c")
    assert not ok and record is None and "bare attach" in why
    ok, _, _ = licensing.founder_attach_check(Manifest(AGPL), {}, "D-LIC-1", "P0")        # P0's own hold too
    assert not ok


def test_d_lic_1_accepts_a_use_specific_clearance_and_returns_the_record_to_journal():
    m = Manifest(UNREAD)
    ok, _, record = licensing.founder_attach_check(m, {"license_clearance": clearance_for(m)}, "D-LIC-1", "P4c")
    assert ok and record["assessment_digest"] == licensing.capability_qualification(m)["assessment_digest"]
    assert record["basis"].startswith("read the license")


@pytest.mark.parametrize("over, says", [
    ({"assessment_digest": "sha256:" + "0" * 64}, "different or earlier assessment"),
    ({"use": {**USE, "network": "serves_users"}}, "use other than"),
    ({"basis": "  "}, "needs a basis"),
    ({"obligations_accepted": []}, "does not accept every obligation"),
])
def test_d_lic_1_refuses_a_stale_or_incomplete_clearance(over, says):
    m = Manifest(UNREAD)
    ok, why, _ = licensing.founder_attach_check(m, {"license_clearance": clearance_for(m, **over)}, "D-LIC-1", "P4c")
    assert not ok and says in why


def test_a_signature_does_not_override_third_party_rights_without_permission_evidence():
    m = Manifest(SSPL)
    ok, why, _ = licensing.founder_attach_check(m, {"license_clearance": clearance_for(m)}, "D-LIC-1", "P4c")
    assert not ok and "third-party rights" in why
    ok, _, record = licensing.founder_attach_check(
        m, {"license_clearance": clearance_for(m, permission="commercial license #123 from the rights holder")},
        "D-LIC-1", "P4c")
    assert ok and record["permission"].startswith("commercial license")


def test_a_clearance_is_revoked_by_any_change_of_facts():
    m = Manifest(UNREAD)
    clearance = clearance_for(m)
    m.provenance["binary_sha256"] = "d" * 64                      # binary replaced after the founder cleared it
    assert licensing.founder_attach_check(m, {"license_clearance": clearance}, "D-LIC-1", "P4c")[0] is False


# -- activation stays the founder's ---------------------------------------------------------------------------

def test_neither_draft_is_active_until_the_founder_adopts_it():
    assert licensing.ACTIVE_BINARY_POLICY == "P0" and licensing.ACTIVE_FOUNDER_ATTACH_POLICY == "P0"
    with pytest.raises(ValueError):
        licensing.attach_check(Manifest(GPL), "P9")


def test_the_founder_attach_hook_is_offered_as_a_patch_that_still_applies_to_body():
    if subprocess.run(["git", "-C", str(REPO), "rev-parse"], capture_output=True).returncode:
        pytest.skip("not a git checkout")
    check = subprocess.run(["git", "-C", str(REPO), "apply", "--check", str(PATCH)], capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
