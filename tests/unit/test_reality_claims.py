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
    assert rc.outcome_levels() == rc.OUTCOME_ORDER == ("self_reported", "internally_observed", "externally_verified")
    assert rc.OUTCOME_CROSSWALK["externally_verified"] == "EXTERNALLY_VERIFIED"
    for name, crosswalk, order in (("directive", rc.DIRECTIVE_CROSSWALK, levels), ("reality", rc.REALITY_CROSSWALK,
                                   REALITY), ("metrics", rc.METRICS_CROSSWALK, rc.METRICS_ORDER),
                                   ("outcome", rc.OUTCOME_CROSSWALK, rc.outcome_levels())):
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
    path.write_text(json.dumps(data) if relative.endswith(".json") else data, encoding="utf-8")


D1, D2, D3, D4 = ("sha256:" + pair * 32 for pair in ("ab", "cd", "ef", "12"))
DEVICE = {"evidence_kind": "founder_device_run", "evidence_ref": D1}
EXTERNAL = {"evidence_kind": "external_verification", "evidence_ref": D2}

# (file, record, why): each ``why`` names one violation the record must produce, and no other violation may occur.
INFLATED = [
    ("docs/evidence/a/run.json", {"reality": "FOUNDER-USED (Linux container rehearsal, test key)"}, "container"),
    ("docs/evidence/b/run.json", {"reality_status": "LIVE-BOUNDED"}, "no declared evidence kind"),
    ("docs/evidence/c/run.json", {"reality": "LOCAL-REAL", "evidence_kind": "unit_test"}, "at most SANDBOX_VERIFIED"),
    ("docs/evidence/d/run.json", {"evidence_level": "FOUNDER_TIER", "evidence_kind": "rehearsal_key"}, "at most BODY"),
    ("docs/evidence/e/run.json", {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run"}, "missing or empty"),
    ("docs/evidence/f/run.json", {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run",
                                  "evidence_ref": f"{D1} docs/evidence/container-run/README.md"}, "describes a container"),
    ("docs/evidence/g/run.json", {"reality": "EXTERNALLY-VERIFIED", **DEVICE}, "at most FOUNDER_ACCEPTED"),
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
    # review round 1, F1/WU13-F1: a label followed by a comma, a dash, "as required" or "open" and a disclaimer
    ("docs/evidence/n1/run.json", {"reality": "FOUNDER-USED, not a rehearsal (Linux container, test key)"}, "container"),
    ("docs/evidence/n2/run.json", {"reality": "FOUNDER-USED: not simulated; ran in a Linux container with a test key"},
     "container"),
    ("docs/evidence/n3/run.json", {"reality": "LIVE-BOUNDED as required, in the CI container"}, "no declared"),
    ("docs/evidence/n4/run.json", {"reality": "LIVE-BOUNDED, required founder grant obtained"}, "no declared"),
    ("docs/evidence/n5/run.json", {"reality": "FOUNDER-USED, pending appraisal (rehearsal key)"}, "rehearsal"),
    ("docs/evidence/n6/run.json", {"reality": "FOUNDER-USED, not a container run"}, "no declared evidence kind"),
    ("docs/evidence/n7/run.json", {"reality": "FOUNDER-USED, not LIVE-BOUNDED"}, "FOUNDER-USED (FOUNDER_ACCEPTED)"),
    ("docs/evidence/n8/run.json", {"reality": "FOUNDER-USED - not simulated"}, "no declared evidence kind"),
    ("docs/evidence/n9/run.json", {"reality": "EXTERNALLY-VERIFIED: not a rehearsal"}, "no declared evidence kind"),
    ("docs/evidence/n10/run.json", {"reality": "FOUNDER-USED as required by section 56"}, "no declared"),
    ("docs/evidence/n11/run.json", {"reality_status": "LIVE-BOUNDED: open for traffic"}, "no declared evidence kind"),
    ("docs/evidence/n12/run.json", {"reality": "LIVE-BOUNDED, still open to buyers"}, "no declared evidence kind"),
    ("docs/evidence/n13/run.json", {"reality": "never failed and labelled FOUNDER-USED"}, "no declared evidence kind"),
    ("docs/evidence/n14/run.json", {"reality": "FOUNDER-USED: pending", "note": "Linux container rehearsal"},
     "container, rehearsal run labelled FOUNDER-USED"),
    ("docs/evidence/n15/run.json", {"reality": "FOUNDER-USED, blocked list cleared"}, "no declared evidence kind"),
    ("docs/evidence/n16/run.json", {"reality": "FOUNDER-USED — deferred work is done"}, "no declared"),
    # F2/WU13-F2/WU13-F3/WU13-F5: a declared kind is checked against the whole record and needs a checkable ref
    ("docs/evidence/o1/run.json", {"reality": "FOUNDER-USED", **DEVICE, "environment": "Linux container"},
     "describes a container run"),
    ("docs/evidence/o2/run.json", {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run",
                                   "evidence_ref": "none"}, "is a placeholder"),
    ("docs/evidence/o3/run.json", {"reality": "EXTERNALLY-VERIFIED", "evidence_kind": "external_verification",
                                   "evidence_ref": "TBD"}, "is a placeholder"),
    ("docs/evidence/o4/run.json", {"reality": "EXTERNALLY-VERIFIED", "evidence_kind": "external_verification",
                                   "evidence_ref": "GitHub Actions ubuntu-latest: pytest tests/integration/test_x.py"},
     ("neither a ledger digest", "describes a GitHub Actions, pytest, ubuntu-latest run")),
    ("docs/evidence/o5/run.json", {"reality": "EXTERNALLY-VERIFIED", "evidence_kind": "external_verification"},
     "missing or empty"),
    ("docs/evidence/o6/run.json", {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run",
                                   "evidence_ref": "sha256:" + "0" * 64}, "neither a ledger digest"),
    ("docs/evidence/o7/run.json", {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run",
                                   "evidence_ref": "docs/evidence/no-such-run/README.md"}, "neither a ledger digest"),
    ("docs/evidence/o8/run.json", {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run",
                                   "evidence_ref": "docs/evidence/o8/run.json"}, "neither a ledger digest"),
    ("docs/evidence/p1/run.json", {"reality": "FOUNDER-USED with the test key", **DEVICE}, "describes a test key run"),
    ("docs/evidence/p2/run.json", {"reality": "FOUNDER-USED", **DEVICE, "how": "a rehearsal"}, "a rehearsal run"),
    ("docs/evidence/p3/run.json", {"reality": "FOUNDER-USED", **DEVICE, "how": "the fixture body"}, "a fixture run"),
    ("docs/evidence/p4/run.json", {"reality": "FOUNDER-USED", **DEVICE, "how": "greg init --no-passphrase"},
     "a --no-passphrase run"),
    ("docs/evidence/p5/run.json", {"reality": "FOUNDER-USED", **DEVICE, "how": "docker compose up"}, "a docker run"),
    ("docs/evidence/p6/run.json", {"reality": "FOUNDER-USED", **DEVICE, "how": "sandboxed"}, "a sandboxed run"),
    ("docs/evidence/p7/run.json", {"reality": "EXTERNALLY-VERIFIED", **EXTERNAL, "run": {"by": "the CI job"}},
     "a CI run"),
    ("docs/evidence/p8/run.json", {"reality": "EXTERNALLY-VERIFIED", **EXTERNAL, "how": "simulated buyer"},
     "a simulated run"),
    ("docs/evidence/p9/run.json", {"reality": "FOUNDER-USED", **DEVICE, "how": "per-test key, throwaway home"},
     "a per-test, throwaway run"),
    # F3: the Outcome contract's validation_status is a claim field
    ("docs/evidence/q1/outcome.json", {"validation_status": "externally_verified", "note": "Linux container, test key"},
     "a container, test key run labelled EXTERNALLY-VERIFIED"),
    ("docs/evidence/q2/outcome.json", {"validation_status": "internally_observed", "evidence_kind": "unit_test"},
     "at most SANDBOX_VERIFIED"),
    # F8: a claim in a list, in a record, in look-alike characters, under a key in another case
    ("docs/evidence/r1/run.json", {"reality": ["UNIT-TESTED", "FOUNDER-USED"]}, "no declared evidence kind"),
    ("docs/evidence/r2/run.json", {"reality": {"level": "FOUNDER-USED"}}, "no declared evidence kind"),
    ("docs/evidence/r3/run.json", {"status": {"tier": "FOUNDER-USED", "evidence_kind": "unit_test"}},
     "at most SANDBOX_VERIFIED"),
    ("docs/evidence/r4/run.json", {"reality": "FOUNDER‐USED (Linux container rehearsal)"}, "container"),
    ("docs/evidence/r5/run.json", {"reality": "EXTERNALLY VERIFIED"}, "no declared evidence kind"),
    ("docs/evidence/r6/run.json", {"reality": "FOUNDER​-USED"}, "no declared evidence kind"),
    ("docs/evidence/r7/run.json", {"reality": "ＦＯＵＮＤＥＲ－ＵＳＥＤ"}, "no declared evidence kind"),
    ("docs/evidence/r8/run.json", {"Reality": "FOUNDER-USED"}, "no declared evidence kind"),
    ("docs/evidence/r9/run.json", {"realityLevel": "FOUNDER-USED"}, "no declared evidence kind"),
    ("docs/evidence/r10/run.json", {"reality": "REBOOT-VERIFIED on the founder device"}, "no declared"),
    ("docs/evidence/r11/run.json", {"reality": "PERSISTENT on the founder's laptop"}, "no declared"),
    ("docs/evidence/r12/run.json", {"status": "live", "note": "container"}, "a container run labelled LIVE"),
    ("docs/evidence/r13/run.json", {"tier": "Live"}, "no declared evidence kind"),
    ("docs/evidence/r14/run.json", {"reality": "EXTERNALLY\tVERIFIED"}, "no declared evidence kind"),
    # scanned beyond docs/: any directory named evidence, YAML there, and JSON anywhere under acceptance/
    ("foundry/evidence/system-99.json", {"status": "FOUNDER-USED"}, "no declared evidence kind"),
    ("evidence/run.json", {"reality": "FOUNDER-USED (container)"}, "container"),
    ("tests/evidence/s/run.yaml", "reality: FOUNDER-USED\n", "no declared evidence kind"),
    ("acceptance/runs/x.json", {"tier": "EXTERNALLY_VERIFIED"}, "no declared evidence kind"),
]

CORRECT = [
    {"reality": "UNIT-TESTED and INTEGRATION-TESTED in a container; not FOUNDER-USED"},
    {"reality": "LOCAL-REAL rehearsal on Linux, test key"},
    {"reality_status": "Nothing built in a container may be labelled FOUNDER-USED, LIVE-BOUNDED or EXTERNALLY-VERIFIED"},
    {"reality": "FOUNDER-USED: pending the founder's run"},
    {"reality": "FOUNDER-USED: not yet"},
    {"reality": "LIVE-BOUNDED is not yet reached"},
    {"reality": "integration-tested, not founder-used"},
    {"reality": "INTEGRATION-TESTED for process death; not REBOOT-VERIFIED on the founder's device"},
    {"evidence_tier": "PREVIOUS ASSISTANT CLAIM (omits founder-device proof)"},
    {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run", "evidence_ref": f"ledger {D1}, closure m:1"},
    {"reality": "EXTERNALLY-VERIFIED", "evidence_kind": "external_verification",
     "evidence_ref": "docs/evidence/receipts/buyer-41.txt"},
    {"reality": "SANDBOXED", "evidence_kind": "unit_test"},
    {"evidence_level": "STRUCTURAL_CANDIDATE", "evidence_kind": "rehearsal_key"},
    {"note": "FOUNDER-USED", "tier": "BODY_VERIFIED"},
    {"status": "a live page was rendered"},
    {"reality": "FOUNDER-USED on the Chromebook; never a container", "evidence_kind": "founder_device_run",
     "evidence_ref": D3},
    {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run", "evidence_ref": D2,
     "history": "earlier it was not run in a container"},
    {"validation_status": "internally_observed"},
    {"validation_status": "self_reported"},
    {"reality": ["UNIT-TESTED", "not FOUNDER-USED"]},
    {"status": {"tier": "FOUNDER-USED", "evidence_kind": "founder_device_run", "evidence_ref": D4}},
]


@pytest.mark.parametrize("relative, data, why", INFLATED)
def test_an_inflated_claim_fails_the_guard(tmp_path, relative, data, why):
    write(tmp_path, relative, data)
    report = rc.scan(tmp_path)
    whys = (why,) if isinstance(why, str) else why
    assert len(report["violations"]) == len(whys), report["violations"]
    for expected in whys:
        assert sum(expected in v["why"] for v in report["violations"]) == 1, (expected, report["violations"])
    assert {v["file"] for v in report["violations"]} == {relative}
    assert report["failing"] == report["violations"] and rc.main(["--root", str(tmp_path)]) == 1


def test_correct_claims_pass_and_schemas_are_not_claims(tmp_path):
    for i, data in enumerate(CORRECT):
        write(tmp_path, f"docs/evidence/ok{i}/run.json", data)
    write(tmp_path, "docs/evidence/receipts/buyer-41.txt", "the buyer's own receipt")
    write(tmp_path, "docs/contract.schema.json", {"status": "FOUNDER-USED"})
    report = rc.scan(tmp_path)
    assert report["failing"] == [] and report["claims"] >= len(CORRECT) and rc.main(["--root", str(tmp_path)]) == 0
    assert report["allowlisted"] == [] and report["stale_allowlist"] == []      # this repository's allowlist stays here


FIELDS = ("reality", "reality_level", "reality_status", "reality_tier", "current_reality", "acceptance_reality",
          "evidence_level", "evidence_tier", "declared_tier", "attained_tier", "tier", "status", "validation_status")


@pytest.mark.parametrize("field", FIELDS)
def test_every_claim_field_is_read(tmp_path, field):
    assert set(rc.CLAIM_FIELDS) == set(FIELDS)
    write(tmp_path, "docs/evidence/a/run.json", {field: "FOUNDER-USED (container)"})
    [violation] = rc.scan(tmp_path)["violations"]
    assert violation["field"] == field and violation["pointer"] == f"/{field}"


SCANNED = {"docs/**/*.json": "docs/a/b.json", "docs/**/*.yaml": "docs/a/b.yaml", "docs/**/*.yml": "docs/b.yml",
           "**/evidence/**/*.json": "organs/x/evidence/run.json", "**/evidence/**/*.yaml": "evidence/x/run.yaml",
           "**/evidence/**/*.yml": "tests/evidence/x/run.yml", "acceptance/**/*.json": "acceptance/a/b.json",
           "greg/path.json": "greg/path.json", "foundry/completion.yaml": "foundry/completion.yaml"}


@pytest.mark.parametrize("pattern", sorted(SCANNED))
def test_every_scanned_location_is_read(tmp_path, pattern):
    assert set(SCANNED) == set(rc.SCAN)
    relative = SCANNED[pattern]
    write(tmp_path, relative, {"reality": "FOUNDER-USED"} if relative.endswith(".json") else "reality: FOUNDER-USED\n")
    assert [v["file"] for v in rc.scan(tmp_path)["violations"]] == [relative]


def test_an_unreadable_file_fails_and_a_bom_or_several_yaml_documents_are_read(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/broken.json").write_text('{"reality": "FOUNDER-USED (container)",}')
    report = rc.scan(tmp_path)
    assert [u["file"] for u in report["unreadable"]] == ["docs/broken.json"] and report["violations"] == []
    assert report["failing"] == report["unreadable"] and rc.main(["--root", str(tmp_path)]) == 1
    (tmp_path / "docs/broken.json").unlink()
    (tmp_path / "docs/bom.json").write_text('﻿{"reality": "FOUNDER-USED (container)"}', encoding="utf-8")
    (tmp_path / "docs/two.yaml").write_text("reality: UNIT-TESTED\n---\nreality: FOUNDER-USED (container)\n")
    report = rc.scan(tmp_path)
    assert report["unreadable"] == []
    assert sorted((v["file"], v["pointer"]) for v in report["violations"]) == [("docs/bom.json", "/reality"),
                                                                              ("docs/two.yaml", "/1/reality")]


def test_an_evidence_ref_must_name_something_checkable(tmp_path):
    write(tmp_path, "docs/evidence/run/README.md", "a run")
    assert rc.ref_problem(D1) is None and rc.ref_problem(f"ledger {D1}, closure m:1") is None
    assert rc.ref_problem("docs/evidence/run/README.md", tmp_path, "docs/x.json") is None
    assert rc.ref_problem("docs/evidence/run/README.md#step-3", tmp_path, "docs/x.json") is None
    for ref in (None, "", "  ", "none", "N/A", "tbd", "TODO", "pending", "?", "-", "sha256:" + "0" * 64,
                "sha256:ab", "docs/evidence/run/README.md", "../outside.txt", "/etc/passwd"):
        assert rc.ref_problem(ref) is not None, ref                       # no root: only a digest resolves
    assert rc.ref_problem("../wu13/README.md", tmp_path, "docs/x.json") is not None
    assert rc.ref_problem("docs/x.json", tmp_path, "docs/x.json") is not None    # a record cannot rest on itself


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


@pytest.mark.parametrize("crosswalk, label", [("DIRECTIVE_CROSSWALK", "PACKAGED"),
                                              ("OUTCOME_CROSSWALK", "self_reported")])
def test_a_broken_crosswalk_fails_the_scan(tmp_path, monkeypatch, crosswalk, label):
    monkeypatch.delitem(getattr(rc, crosswalk), label)
    report = rc.scan(tmp_path)
    assert report["violations"] == [] and report["failing"] == report["crosswalk_problems"]
    assert f"unmapped ['{label}']" in report["failing"][0]["crosswalk"] and rc.main(["--root", str(tmp_path)]) == 1


def test_the_repository_claims_stay_within_their_evidence():
    """The guard over this tree: any new inflated claim, unreadable file or stale allowlist entry fails here. Every
    allowlisted violation is still reported, with its reason and owner."""
    report = rc.scan()
    assert report["failing"] == [], json.dumps(report["failing"], indent=1)
    assert report["unreadable"] == []
    assert {(a["file"], a["pointer"], a["claimed"]) for a in report["allowlisted"]} == set(rc.ALLOWLIST)
    assert all(a["allowlisted"]["reason"] and a["allowlisted"]["owner"] for a in report["allowlisted"])
