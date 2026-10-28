"""Resolutions bind to real founder-signed envelopes on a body (review of #210, S1, S2, S9).

A per-test Ed25519 founder key signs every REALIZATION through the body's own command path; settlement reads the
verified envelopes through ``goal_gravity.signed_commands``. Values are synthetic test inputs.
"""
from __future__ import annotations

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.cognition import settlement  # noqa: E402
from tests.unit.test_greg_construction_realization import PROMISED, Run  # noqa: E402
from tests.unit.test_greg_recombine import PORTFOLIO  # noqa: E402


def objective_facts(journal):
    return {e.payload["source"] + ":" + repr(e.payload["realized"]): e.event_id
            for e in journal.replay("cognition.realization") if e.payload.get("kind") == "objective"}


def signed_report_digest(journal):
    return next(e.payload["digest"] for e in journal.replay("command.accepted")
                if e.payload.get("kind") == "REALIZATION" and "resolves" not in (e.payload.get("envelope") or {})
                .get("body", {}))


def test_only_a_resolution_the_founder_actually_signed_resolves_a_dispute(tmp_path):
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-signed", PORTFOLIO)
        run.realize(record, PROMISED - 2, source="founder_reported")
        run.realize(record, PROMISED, source="external_record")
        ids = objective_facts(journal)
        assert set(ids) == {"founder_reported:0", "external_record:2"}
        [row] = [r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict"]
        external = next(r for r in row["reports"] if r["declared_source"] == "external_record")
        assert external["eligible_to_accept"] is True and external["signed_command"]

        # S1: the founder's ordinary signed report's digest, borrowed by a resolution written in-process
        journal.record("cognition.realization", {
            "receipt": record.hash, "kind": "resolution", "resolves": list(ids.values()),
            "accept": ids["external_record:2"], "note": "borrowed", "authority_created": False,
            "command_digest": signed_report_digest(journal)}, key=["forged"])
        # and a bare acceptance record with no envelope
        journal.record("command.accepted", {"kind": "REALIZATION", "digest": "sha256:bare"}, key=["bare"])
        journal.record("cognition.realization", {
            "receipt": record.hash, "kind": "resolution", "resolves": list(ids.values()),
            "accept": ids["external_record:2"], "note": "bare", "authority_created": False,
            "command_digest": "sha256:bare"}, key=["bare-resolution"])
        assert run.outcome(record) is None                          # still disputed: neither credited

        # S2: a signed invalidation that leaves the founder report standing is refused
        with pytest.raises(ValueError, match="names every live report"):
            run.command("REALIZATION", {"receipt": record.hash, "resolves": [ids["external_record:2"]],
                                        "note": "partial"})

        # the real signed resolution counts
        run.command("REALIZATION", {**row["prepared_resolution"]["body"], "note": "time-clock export"})
        outcome = run.outcome(record)
        assert outcome["world"]["state"] == "adjudicated" and outcome["correct"] is True
        assert "declared by the reporter, not verified" in outcome["evidence_tier"]


def test_s3_on_a_body_an_independent_report_matching_a_conflicting_value_is_recorded(tmp_path):
    """The body's journal is keyed: a conflict key without the source dropped this report (review of #210, S3)."""
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-s3", PORTFOLIO)
        run.realize(record, PROMISED - 1, source="founder_reported")
        run.realize(record, PROMISED, source="founder_reported")
        run.realize(record, PROMISED, source="external_record")
        assert set(objective_facts(journal)) == {"founder_reported:1", "founder_reported:2", "external_record:2"}
        [row] = [r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict"]
        assert row["resolvable_now"] is True
