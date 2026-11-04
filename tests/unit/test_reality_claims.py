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
    # review round 2, WU13-R2-5: section 56's levels are not collapsed into the coarse rungs
    assert {kind: c["directive"] for kind, c in rc.CEILINGS.items()} == {
        "unit_test": "UNIT-TESTED", "integration_container": "PERSISTENT", "rehearsal_key": "PERSISTENT",
        "founder_device_run": "FOUNDER-USED", "external_verification": "EXTERNALLY-VERIFIED"}
    levels = rc.directive_levels()
    assert all(c["directive"] in levels for c in rc.CEILINGS.values())


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


def template_labels(text: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index("### Current reality")
    return [line[6:].strip() for line in lines[start:] if line.startswith("- [ ] ")][:13]


def test_every_reality_label_the_sop_and_its_templates_offer_is_read():
    """Review round 2, WU13-A2: MAC-VERIFIED, a reality label of the cognition SOP and of the PR and Discussion
    templates, was in no crosswalk, so a container run labelled with it passed."""
    import yaml
    root = Path(rc.ROOT)
    sop = rc.sop_levels()
    pr = template_labels((root / ".github/PULL_REQUEST_TEMPLATE.md").read_text())
    form = yaml.safe_load((root / ".github/DISCUSSION_TEMPLATE/general.yml").read_text())
    [field] = [b for b in form["body"] if b.get("id") == "reality"]
    offered = set(sop) | set(pr) | set(field["attributes"]["options"])
    assert "MAC-VERIFIED" in sop and set(pr) == set(sop) == set(field["attributes"]["options"])
    assert all(label in rc.NOT_RUNGS or label in rc.LABELS for label in offered), offered - set(rc.LABELS)
    assert rc.LABELS["MAC-VERIFIED"] == rc.LABELS["CHROMEBOOK-VERIFIED"] == "FOUNDER_ACCEPTED"
    assert rc.crosswalk_problems() == []                    # the SOP's list is no order: checked total, not monotone
    for label in sop:
        if label in rc.NOT_RUNGS:
            continue
        partial = {k: v for k, v in rc.SOP_CROSSWALK.items() if k != label}
        [problem] = rc.crosswalk_problems(crosswalks={"sop": (sop, partial, False)})
        assert f"'{label}'" in problem and "unmapped" in problem


def test_one_label_maps_to_one_rung_in_every_vocabulary_and_every_ceiling_is_a_level(monkeypatch):
    monkeypatch.setitem(rc.SOP_CROSSWALK, "SANDBOXED", "BODY_VERIFIED")
    assert any("SANDBOXED: one label maps to several rungs" in p for p in rc.crosswalk_problems())
    monkeypatch.setitem(rc.SOP_CROSSWALK, "SANDBOXED", "SANDBOX_VERIFIED")
    monkeypatch.setitem(rc.CEILINGS["unit_test"], "directive", "LOCAL-REAL")
    assert rc.crosswalk_problems() == ["ceiling unit_test: section-56 level LOCAL-REAL is above its rung "
                                       "SANDBOX_VERIFIED"]
    monkeypatch.setitem(rc.CEILINGS["unit_test"], "directive", "UNIT-VERIFIED")
    assert rc.crosswalk_problems() == ["ceiling unit_test: 'UNIT-VERIFIED' is not a section-56 level"]


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
    ("docs/evidence/n17/run.json", {"reality": "FOUNDER-USED (blocked list cleared)"}, "no declared evidence kind"),
    # F2/WU13-F2/WU13-F3/WU13-F5: a declared kind is checked against the whole record and needs a checkable ref
    ("docs/evidence/o1/run.json", {"reality": "FOUNDER-USED", **DEVICE, "environment": "Linux container"},
     "describes a container run"),
    ("docs/evidence/o2/run.json", {"reality": "FOUNDER-USED", "evidence_kind": "founder_device_run",
                                   "evidence_ref": "none"}, "is a placeholder"),
    ("docs/evidence/o3/run.json", {"reality": "EXTERNALLY-VERIFIED", "evidence_kind": "external_verification",
                                   "evidence_ref": "TBD"}, "is a placeholder"),
    ("docs/evidence/o4/run.json", {"reality": "EXTERNALLY-VERIFIED", "evidence_kind": "external_verification",
                                   "evidence_ref": "GitHub Actions ubuntu-latest: pytest tests/integration/test_x.py"},
     ("neither a ledger digest", "describes a GitHub Actions, pytest, tests/integration/, ubuntu-latest run")),
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
    # review round 2, WU13-A1 and WU13-R2-2: a negator reaches a label only across function words, and across another
    # label only with "or" or "nor"; a comma ends it; "above" and "beyond" claim more
    ("docs/evidence/s1/run.json", {"reality": "Not UNIT-TESTED, FOUNDER-USED", "run": "Linux container rehearsal"},
     "container, rehearsal run labelled FOUNDER-USED"),
    ("docs/evidence/s2/run.json", {"reality": "never ran on the founder's device, FOUNDER-USED"}, "no declared"),
    ("docs/evidence/s3/run.json", {"evidence_kind": "integration_container", "host": "docker",
                                   "reality": "not run on the founder's device, FOUNDER-USED"},
     "integration_container establishes at most BODY_VERIFIED"),
    ("docs/evidence/s4/run.json", {"reality": "not UNIT-TESTED FOUNDER-USED"}, "no declared evidence kind"),
    ("docs/evidence/s5/run.json", {"reality": "at or above FOUNDER-USED (container rehearsal, test key)"},
     "container, rehearsal, test key run labelled FOUNDER-USED"),
    ("docs/evidence/s6/run.json", {"reality": "beyond LOCAL-REAL, FOUNDER-USED (container rehearsal)"},
     "container, rehearsal run labelled FOUNDER-USED"),
    ("docs/evidence/s7/run.json", {"validation_status": "beyond EXTERNALLY-VERIFIED", "note": "pytest"},
     "pytest run labelled EXTERNALLY-VERIFIED"),
    ("docs/evidence/s8/run.json", {"reality": "above FOUNDER-USED"}, "no declared evidence kind"),
    ("docs/evidence/s9/run.json", {"reality": "not built in a container, FOUNDER-USED"}, "no declared evidence kind"),
    ("docs/evidence/s10/run.json", {"reality": "never ran FOUNDER-USED"}, "no declared evidence kind"),
    ("docs/evidence/s11/run.json", {"reality": "not the founder's own device FOUNDER-USED"}, "no declared"),
    # WU13-A2: a device-verified label, a suffixed label
    ("docs/evidence/t1/run.json", {"reality": "MAC-VERIFIED", "run": "docker container"},
     "container, docker run labelled MAC-VERIFIED"),
    ("docs/evidence/t2/run.json", {"reality": "CHROMEBOOK-VERIFIED"}, "CHROMEBOOK-VERIFIED (FOUNDER_ACCEPTED)"),
    ("docs/evidence/t3/run.json", {"reality": "EXTERNALLY_VERIFIED_OUTCOME", "run": "docker"},
     "docker run labelled EXTERNALLY-VERIFIED"),
    ("docs/evidence/t4/run.json", {"reality": "FOUNDER-USED-ON-DEVICE", "run": "docker"},
     "docker run labelled FOUNDER-USED"),
    ("docs/evidence/t5/run.json", {"reality": "Mac/Chromebook-verified"}, "DEVICE-VERIFIED (FOUNDER_ACCEPTED)"),
    # WU13-R2-3 and WU13-A2: "live" opening a value or after a colon
    ("docs/evidence/t6/run.json", {"reality": "Live (Linux container rehearsal, test key)"},
     "container, rehearsal, test key run labelled LIVE"),
    ("docs/evidence/t7/run.json", {"status": "Live on the Chromebook container"}, "container run labelled LIVE"),
    ("docs/evidence/t8/run.json", {"reality": "live in production", "host": "docker container"},
     "container, docker run labelled LIVE"),
    ("docs/evidence/t9/run.json", {"reality": "status: live"}, "LIVE (AUTHORIZED_LIVE)"),
    # WU13-A7: an item under a claim field keeps its own declared kind
    ("docs/evidence/u1/run.json", {"evidence_kind": "external_verification", "evidence_ref": D2,
                                   "status": [{"reality": "EXTERNALLY-VERIFIED", "evidence_kind": "integration_container"}]},
     "integration_container establishes at most BODY_VERIFIED"),
    # WU13-A11: a record that declares no kind is held to the kind its own evidence names
    ("docs/evidence/v1/run.json", {"reality": "LOCAL-REAL", "evidence": "unit tests in a sandbox"}, "held to unit_test"),
    ("docs/evidence/v2/run.json", {"reality": "INTEGRATION-TESTED (in-process unit tests)"}, "at most UNIT-TESTED"),
    ("docs/evidence/v3/run.json", {"reality": "REBOOT-VERIFIED in a Linux container"},
     "held to integration_container"),
    ("docs/evidence/v4/run.json", {"reality": "REBOOT-VERIFIED", "how": "greg rehearse with a test key"},
     "held to rehearsal_key"),
    # WU13-R2-5: a declared kind's section-56 ceiling
    ("docs/evidence/w1/run.json", {"evidence_kind": "unit_test", "reality": "INTEGRATION-TESTED"}, "at most UNIT-TESTED"),
    ("docs/evidence/w2/run.json", {"evidence_kind": "unit_test", "reality": "SANDBOXED"}, "at most UNIT-TESTED"),
    ("docs/evidence/w3/run.json", {"evidence_kind": "rehearsal_key", "reality": "INSTALLED, PERSISTENT, REBOOT-VERIFIED"},
     "rehearsal_key establishes at most PERSISTENT"),
    ("docs/evidence/w4/run.json", {"evidence_kind": "integration_container",
                                   "reality": "SANDBOX_VERIFIED, REBOOT-VERIFIED"}, "at most PERSISTENT"),
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
    {"reality": "SANDBOX_VERIFIED", "evidence_kind": "unit_test"},     # the acceptance rung; SANDBOXED is above UNIT-TESTED
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
    # review round 2: honest negations, kinds and lists that must still pass
    {"reality": "not FOUNDER-USED or LIVE-BOUNDED"},
    {"reality": "neither FOUNDER-USED nor LIVE-BOUNDED"},
    {"reality": "INTEGRATION-TESTED; never ran on the founder's device"},
    {"reality_status": "IMPLEMENTED, TESTED; not founder-used, not MAC/Chromebook-verified"},
    {"reality": "below FOUNDER-USED"},
    {"reality": "UNIT-TESTED (unit tests, in-process)", "evidence_kind": "unit_test"},
    {"reality": "PERSISTENT", "evidence_kind": "integration_container"},
    {"reality": "INTEGRATION-TESTED", "evidence": "unit and integration tests in a container"},
    {"reality": "LOCAL-REAL", "evidence": "integration tests in a container"},
    # a directory names no kind: tests/unit/ holds real-process tests here (acceptance/missions.json)
    {"reality": "LOCAL-REAL", "evidence": "pytest tests/unit/test_x.py in a sandbox"},
    {"status": "liveness probe passed"},
    # only the claim and its statement of evidence name the kind, never notes about other tests
    {"tier": "BODY_VERIFIED", "notes": "in-process unit tests cover the parsing; the cited process test runs greg run"},
    # each item of a list under a claim field is its own record: the second item's docker run is not the first's
    {"evidence_kind": "founder_device_run", "evidence_ref": D1,
     "status": [{"reality": "FOUNDER-USED"}, {"reality": "UNIT-TESTED", "evidence_kind": "unit_test", "how": "docker"}]},
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


SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
          "properties": {"status": {"enum": ["FOUNDER-USED", "LIVE"], "default": "FOUNDER-USED"},
                         "reality": {"const": "EXTERNALLY-VERIFIED", "examples": ["FOUNDER-USED (container)"]}},
          "$defs": {"tier": {"type": "string", "enum": ["FOUNDER_ACCEPTED"]}}}


def test_correct_claims_pass_and_schemas_are_not_claims(tmp_path):
    for i, data in enumerate(CORRECT):
        write(tmp_path, f"docs/evidence/ok{i}/run.json", data)
    write(tmp_path, "docs/evidence/receipts/buyer-41.txt", "the buyer's own receipt")
    write(tmp_path, "docs/contract.schema.json", SCHEMA)
    write(tmp_path, "docs/evidence/shape.json", SCHEMA)                      # a schema by content, whatever its name
    report = rc.scan(tmp_path)
    assert report["failing"] == [] and report["claims"] >= len(CORRECT) and rc.main(["--root", str(tmp_path)]) == 0
    assert report["allowlisted"] == [] and report["stale_allowlist"] == []      # this repository's allowlist stays here


@pytest.mark.parametrize("relative, text, pointer", [
    ("docs/evidence/zz/run.schema.json", json.dumps({"reality": "FOUNDER-USED (container)"}), "/reality"),
    ("docs/evidence/zz/run.JSON", json.dumps({"reality": "FOUNDER-USED (container)"}), "/reality"),
    ("docs/evidence/zz/run.jsonl", '{"reality": "UNIT-TESTED"}\n\n{"reality": "FOUNDER-USED (container)"}\n', "/2/reality"),
    ("acceptance/zz.yaml", "reality: FOUNDER-USED (container)\n", "/reality"),
    ("docs/evidence/zz/instance.json", json.dumps({"$schema": SCHEMA["$schema"], "reality": "FOUNDER-USED (container)"}),
     "/reality"),
])
def test_no_file_shape_or_schema_reference_hides_a_claim(tmp_path, relative, text, pointer):
    """Review round 2, WU13-A10: a name ending .schema.json, an upper-case extension, JSON Lines, YAML under acceptance/
    and a record that only names a schema were never read."""
    (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / relative).write_text(text)
    [violation] = rc.scan(tmp_path)["violations"]
    assert (violation["file"], violation["pointer"]) == (relative, pointer)


def test_a_file_nested_past_the_recursion_limit_is_unreadable_not_a_traceback(tmp_path, capsys):
    """Review round 2, WU13-A8."""
    (tmp_path / "docs/evidence/zz").mkdir(parents=True)
    (tmp_path / "docs/evidence/zz/deep.json").write_text("[" * 5000 + "]" * 5000)
    (tmp_path / "docs/evidence/zz/deep.yaml").write_text("reality: " + "[" * 5000 + "]" * 5000 + "\n")
    report = rc.scan(tmp_path)
    assert sorted(u["file"] for u in report["unreadable"]) == ["docs/evidence/zz/deep.json", "docs/evidence/zz/deep.yaml"]
    assert all("RecursionError" in u["why"] for u in report["unreadable"]) and report["failing"] == report["unreadable"]
    assert rc.main(["--root", str(tmp_path)]) == 1 and "2 unreadable" in capsys.readouterr().err


FIELDS = ("reality", "reality_level", "reality_status", "reality_tier", "current_reality", "acceptance_reality",
          "evidence_level", "evidence_tier", "declared_tier", "attained_tier", "tier", "status", "validation_status")


@pytest.mark.parametrize("field", FIELDS)
def test_every_claim_field_is_read(tmp_path, field):
    assert set(rc.CLAIM_FIELDS) == set(FIELDS)
    write(tmp_path, "docs/evidence/a/run.json", {field: "FOUNDER-USED (container)"})
    [violation] = rc.scan(tmp_path)["violations"]
    assert violation["field"] == field and violation["pointer"] == f"/{field}"


SCANNED = ["docs/a/b.json", "docs/a/b.yaml", "docs/b.yml", "docs/c.jsonl", "docs/D.JSON", "organs/x/evidence/run.json",
           "evidence/x/run.yaml", "tests/evidence/x/run.yml", "tests/evidence/x/run.jsonl", "foundry/evidence/s.Json",
           "acceptance/a/b.json", "acceptance/c.yaml", "acceptance/d.YML", "greg/path.json", "foundry/completion.yaml"]
NOT_SCANNED = ["contracts/x.json", "greg/other.json", "foundry/other.yaml", "docs/a.txt", "docs/evidence/a.md",
               "evidenced/x.json", "src/acceptance/x.json"]


@pytest.mark.parametrize("relative", SCANNED)
def test_every_scanned_location_is_read(tmp_path, relative):
    assert (rc.SCAN_DIRS, rc.SCAN_SUFFIXES, rc.SCAN_FILES) == (
        ("docs", "acceptance"), (".json", ".jsonl", ".yaml", ".yml"), ("greg/path.json", "foundry/completion.yaml"))
    suffix = relative.rsplit(".", 1)[1].lower()
    (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / relative).write_text('{"reality": "FOUNDER-USED"}' if suffix.startswith("json") else "reality: FOUNDER-USED\n")
    assert rc.scanned(relative) and [v["file"] for v in rc.scan(tmp_path)["violations"]] == [relative]


def test_nothing_else_is_read(tmp_path):
    for relative in NOT_SCANNED:
        write(tmp_path, relative, {"reality": "FOUNDER-USED"} if relative.endswith(".json") else "reality: FOUNDER-USED\n")
        assert not rc.scanned(relative), relative
    (tmp_path / ".git" / "evidence").mkdir(parents=True)
    (tmp_path / ".git" / "evidence" / "x.json").write_text(json.dumps({"reality": "FOUNDER-USED"}))
    assert rc.scan(tmp_path)["files"] == 0


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
    assert rc.ref_problem("docs/x.json", tmp_path, "docs/x.json") is not None    # a record cannot rest on itself
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"                   # a file that exists, outside the tree
    outside.write_text("not this repository's")
    try:
        assert rc.ref_problem(f"../{outside.name}", tmp_path, "docs/x.json") is not None
        assert rc.ref_problem(str(outside), tmp_path, "docs/x.json") is not None
        assert rc.ref_problem(str(tmp_path / "docs/evidence/run/README.md"), tmp_path, "docs/x.json") is not None
    finally:
        outside.unlink()


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
                                              ("OUTCOME_CROSSWALK", "self_reported"), ("SOP_CROSSWALK", "TESTED")])
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
