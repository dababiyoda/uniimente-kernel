"""No machine-readable claim sits above what its evidence kind can establish (directive section 56).

Founder correction of 2026-10-30: nothing built in a container is labelled founder-used, live or externally verified.
The guard reuses the ladders that exist (the acceptance harness's, which foundry.completion shares, plus
greg.metrics and greg.mission_control.REALITY) and maps the directive's seventeen levels onto them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import acceptance
from foundry.completion import EVIDENCE_TIERS
from acceptance import claims as rc
from greg import metrics
from greg.mission_control import REALITY


def test_one_existing_ladder_and_one_table_of_evidence_kinds():
    assert acceptance.STATUSES == EVIDENCE_TIERS                     # the acceptance and Foundry ladders are one
    assert set(rc.CEILINGS) == {"unit_test", "integration_container", "rehearsal_key", "founder_device_run",
                                "external_verification"}
    for kind in ("unit_test", "integration_container", "rehearsal_key"):    # test, container and rehearsal evidence
        assert acceptance.rank(rc.CEILINGS[kind]["ladder"]) <= acceptance.rank(acceptance.TEST_TIERS[-1])
        assert rc.CEILINGS[kind]["metrics"] == metrics.STRUCTURAL_CANDIDATE
    assert rc.CEILINGS["unit_test"]["ladder"] == "SANDBOX_VERIFIED"
    assert rc.CEILINGS["founder_device_run"]["ladder"] in acceptance.BEYOND_TESTS
    assert rc.CEILINGS["founder_device_run"]["metrics"] == metrics.FOUNDER_TIER
    assert rc.CEILINGS["external_verification"]["ladder"] == "EXTERNALLY_VERIFIED"
    assert all(c["basis"] for c in rc.CEILINGS.values()) and rc.TEST_CEILING == "BODY_VERIFIED"


def test_the_crosswalk_is_total_and_monotone_and_removing_a_mapping_fails():
    levels = rc.directive_levels()
    assert len(levels) == 17 and levels[0] == "ASPIRATIONAL" and levels[-1] == "PRODUCTION-AUTHORIZED"
    assert set(rc.REALITY_CROSSWALK) == set(REALITY) and rc.crosswalk_problems() == []
    assert rc.DIRECTIVE_CROSSWALK["FOUNDER-USED"] == "FOUNDER_ACCEPTED"
    assert rc.REALITY_CROSSWALK["FOUNDER-DEVICE-VERIFIED"] == "FOUNDER_ACCEPTED"
    assert rc.METRICS_CROSSWALK[metrics.FOUNDER_TIER] == "FOUNDER_ACCEPTED"
    for name, crosswalk, order in (("directive", rc.DIRECTIVE_CROSSWALK, levels), ("reality", rc.REALITY_CROSSWALK,
                                   REALITY), ("metrics", rc.METRICS_CROSSWALK, rc.METRICS_ORDER)):
        for label in order:
            partial = {k: v for k, v in crosswalk.items() if k != label}
            [problem] = rc.crosswalk_problems(crosswalks={name: (order, partial)})
            assert f"unmapped ['{label}']" in problem
        inverted = {**crosswalk, order[0]: "COMMERCIAL_OUTCOME_VERIFIED"}
        assert any("not monotone" in p for p in rc.crosswalk_problems(crosswalks={name: (order, inverted)}))
        assert rc.crosswalk_problems(crosswalks={name: (order, {**crosswalk, order[0]: "LIVE"})})
    assert rc.crosswalk_problems(levels=levels[:-1])                       # a level the directive lists is unknown


def write(root: Path, relative: str, data) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if relative.endswith(".json") else data)


INFLATED = [
    ("docs/evidence/a/run.json", {"reality": "FOUNDER-USED (Linux container rehearsal, test key)"}, "container"),
    ("docs/evidence/b/run.json", {"reality_status": "LIVE-BOUNDED"}, "no declared evidence kind"),
    ("docs/evidence/c/run.json", {"reality": "LOCAL-REAL", "evidence_kind": "unit_test"}, "at most SANDBOX_VERIFIED"),
    ("docs/evidence/d/run.json", {"evidence_level": "FOUNDER_TIER", "evidence_kind": "rehearsal_key"}, "at most BODY"),
    ("docs/evidence/e/run.json", {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run"}, "evidence_ref"),
    ("docs/evidence/f/run.json", {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run",
                                  "evidence_ref": "docs/evidence/container-run/README.md"}, "describes a container"),
    ("docs/evidence/g/run.json", {"reality": "EXTERNALLY-VERIFIED", "evidence_kind": "founder_device_run",
                                  "evidence_ref": "ledger sha256:ab"}, "at most FOUNDER_ACCEPTED"),
    ("docs/evidence/h/run.json", {"reality": "FOUNDER-DEVICE-VERIFIED"}, "no declared evidence kind"),
    ("docs/evidence/i/run.json", {"current_reality": "REBOOT-VERIFIED on the founder's device"}, "no declared"),
    ("docs/evidence/j/run.json", {"status": "COMMERCIALLY-VALIDATED", "evidence_kind": "vibes"}, "not one of"),
    ("docs/evidence/j2/run.json", {"status": "UNIT-TESTED", "evidence_kind": ["unit_test"]}, "not one of"),
    ("docs/evidence/k/run.json", {"reality": "not a container, FOUNDER-USED"}, "no declared evidence kind"),
    ("docs/evidence/l/run.json", {"reality": "externally verified by the buyer"}, "no declared evidence kind"),
    ("docs/evidence/m/run.json", {"tier": "LIVE", "note": "rehearsal on Linux"}, "rehearsal run labelled LIVE"),
    ("docs/evidence/m2/run.json", {"reality": "Simulated: no. FOUNDER-USED"}, "no declared evidence kind"),
    ("docs/evidence/m3/run.json", {"reality": "FOUNDER-USED (not a container run)"}, "no declared evidence kind"),
    ("acceptance/extra.json", {"requirements": [{"tier": "EXTERNALLY_VERIFIED"}]}, "no declared evidence kind"),
    ("tests/evidence/n/summary.json", [{"reality_level": "PRODUCTION-AUTHORIZED"}], "no declared evidence kind"),
    ("foundry/completion.yaml", "9:\n  state: COMPLETE\n  evidence_tier: FOUNDER_ACCEPTED\n", "no declared"),
    ("greg/path.json", {"horizons": [{"id": "h1", "current_reality": "FOUNDER-USED on the Chromebook"}]}, "no decl"),
]

CORRECT = [
    {"reality": "UNIT-TESTED and INTEGRATION-TESTED in a container; not FOUNDER-USED"},
    {"reality": "LOCAL-REAL rehearsal on Linux, test key"},
    {"reality_status": "Nothing built in a container may be labelled FOUNDER-USED, LIVE-BOUNDED or EXTERNALLY-VERIFIED"},
    {"reality": "FOUNDER-USED: pending the founder's run"},
    {"reality": "INTEGRATION-TESTED for process death; not REBOOT-VERIFIED on the founder's device"},
    {"evidence_tier": "PREVIOUS ASSISTANT CLAIM (omits founder-device proof)"},
    {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run", "evidence_ref": "ledger sha256:ab, closure m:1"},
    {"reality": "EXTERNALLY-VERIFIED", "evidence_kind": "external_verification", "evidence_ref": "buyer receipt 41"},
    {"reality": "SANDBOXED", "evidence_kind": "unit_test"},
    {"evidence_level": "STRUCTURAL_CANDIDATE", "evidence_kind": "rehearsal_key"},
    {"note": "FOUNDER-USED", "tier": "BODY_VERIFIED"},
    {"status": "a live page was rendered"},
    {"reality": "FOUNDER-USED on the Chromebook; never a container", "evidence_kind": "founder_device_run",
     "evidence_ref": "ledger sha256:ef"},
    {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run", "evidence_ref": "ledger sha256:cd",
     "history": "earlier it was not run in a container"},
]


@pytest.mark.parametrize("relative, data, why", INFLATED)
def test_an_inflated_claim_fails_the_guard(tmp_path, relative, data, why):
    write(tmp_path, relative, data)
    report = rc.scan(tmp_path)
    [violation] = report["violations"]
    assert violation["file"] == relative and why in violation["why"], violation
    assert report["failing"] == [violation] and rc.main(["--root", str(tmp_path)]) == 1


def test_correct_claims_pass_and_schemas_are_not_claims(tmp_path):
    for i, data in enumerate(CORRECT):
        write(tmp_path, f"docs/evidence/ok{i}/run.json", data)
    write(tmp_path, "docs/contract.schema.json", {"status": "FOUNDER-USED"})
    (tmp_path / "docs/broken.json").write_text("{not json")
    report = rc.scan(tmp_path)
    assert report["failing"] == [] and report["claims"] >= len(CORRECT) and rc.main(["--root", str(tmp_path)]) == 0
    assert [u["file"] for u in report["unreadable"]] == ["docs/broken.json"]


def test_a_violation_another_change_owns_is_allowlisted_with_reason_and_owner_never_silently(tmp_path):
    write(tmp_path, "docs/evidence/a/run.json", {"reality": "FOUNDER-USED (container)"})
    key = ("docs/evidence/a/run.json", "/reality", "FOUNDER-USED")
    owned = rc.scan(tmp_path, allowlist={key: {"reason": "PR #999 owns this record", "owner": "session x"}})
    assert owned["failing"] == [] and owned["allowlisted"][0]["allowlisted"]["owner"] == "session x"
    assert owned["allowlisted"][0]["claimed"] == "FOUNDER-USED"                  # still reported
    assert rc.scan(tmp_path, allowlist={key: {"reason": "", "owner": "session x"}})["failing"]
    write(tmp_path, "docs/evidence/a/run.json", {"reality": "LOCAL-REAL (container)"})
    stale = rc.scan(tmp_path, allowlist={key: {"reason": "PR #999", "owner": "session x"}})
    assert stale["violations"] == [] and stale["failing"] == stale["stale_allowlist"] and stale["failing"]


def test_a_broken_crosswalk_fails_the_scan(tmp_path, monkeypatch):
    monkeypatch.delitem(rc.DIRECTIVE_CROSSWALK, "PACKAGED")
    report = rc.scan(tmp_path)
    assert report["violations"] == [] and report["failing"] == report["crosswalk_problems"]
    assert "unmapped ['PACKAGED']" in report["failing"][0]["crosswalk"] and rc.main(["--root", str(tmp_path)]) == 1


def test_the_repository_claims_stay_within_their_evidence():
    """The guard over this tree: any new inflated claim (or a stale allowlist entry) fails here."""
    report = rc.scan()
    assert report["failing"] == [], json.dumps(report["failing"], indent=1)
    assert report["unreadable"] == []
