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


# --- integrator intake conditions for goal_gravity.EVIDENCE_KINDS (#196 integrator, 2026-10-28) ---------------------


def test_a_verified_realization_changes_no_goal_mission_or_verified_kind_fact(tmp_path, monkeypatch):
    """Conditions 1 and 3: with and without EVIDENCE_KINDS, every founder fact other than the REALIZATION entries,
    the mission book and signed_commands(*VERIFIED_KINDS) are identical."""
    from greg import goal_gravity
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-facts", PORTFOLIO)
        run.realize(record, PROMISED - 2, source="founder_reported")
        run.realize(record, PROMISED, source="external_record")
        new = goal_gravity.founder_facts(journal.ledger)
        verified_new = goal_gravity.signed_commands(journal, *goal_gravity.VERIFIED_KINDS)
        with monkeypatch.context() as before:
            before.setattr(goal_gravity, "EVIDENCE_KINDS", ())
            old = goal_gravity.founder_facts(journal.ledger)
            verified_old = goal_gravity.signed_commands(journal, *goal_gravity.VERIFIED_KINDS)
        realization = {d for d, c in new.signed.items() if c["kind"] == "REALIZATION"}
        assert len(realization) == 2 and not any(c["kind"] == "REALIZATION" for c in old.signed.values())
        assert {d: c for d, c in new.signed.items() if d not in realization} == old.signed
        assert {d: e for d, e in new.signed_at.items() if d not in realization} == old.signed_at
        assert {d: r for d, r in new.refused.items() if d not in realization} == old.refused
        for name in ("admitted", "specs", "closed", "closed_intents", "stop", "narrowing", "floor", "controlled_at",
                     "authorizations", "revoked", "enrolled_at"):
            assert getattr(new, name) == getattr(old, name), name
        assert ({m: (b.status, b.spec) for m, b in new.book.missions.items()}
                == {m: (b.status, b.spec) for m, b in old.book.missions.items()})
        assert verified_new == verified_old


def test_a_realization_whose_envelope_fails_still_records_its_value_but_can_ground_nothing(tmp_path):
    """Condition 2: a stale or nonce-replayed REALIZATION the ledger shows as accepted keeps its value as a report,
    exactly as before; it is only ineligible to be accepted (and cannot carry a resolution)."""
    from datetime import datetime, timedelta, timezone
    from greg.founder import sign_command, stamp
    from provenance.ledger import sha256_json
    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-stale", PORTFOLIO)
        run.realize(record, PROMISED - 2, source="founder_reported")
        earlier_nonce = next(e.payload["nonce"] for e in journal.replay("command.accepted")
                             if e.payload.get("kind") == "REALIZATION")

        def accepted(body, *, now=None, ttl=timedelta(hours=1), nonce=None):
            env = sign_command(run.key, "REALIZATION", body, body_id=run.body_id, now=now, ttl=ttl, nonce=nonce)
            digest = sha256_json(env)
            settlement.record_realization(journal, receipt=body["receipt"], realized=body["realized"],
                                          source=body["source"], note=body["note"], command_digest=digest)
            journal.record("command.accepted", {"kind": "REALIZATION", "digest": digest, "nonce": env["nonce"],
                                                "founder_key_id": env["founder_key_id"], "signer": "founder",
                                                "issued_at": env["issued_at"],
                                                "accepted_at": stamp(datetime.now(timezone.utc)),
                                                "envelope": env, "channel": "test", "result": {}}, key=digest)
            return digest

        stale = accepted({"receipt": record.hash, "realized": PROMISED, "source": "external_record", "note": ""},
                         now=datetime.now(timezone.utc) - timedelta(days=2))
        replayed = accepted({"receipt": record.hash, "realized": PROMISED, "source": "sensor_observation",
                             "note": ""}, nonce=earlier_nonce)
        facts = {e.payload["command_digest"]: e for e in journal.replay("cognition.realization")
                 if e.payload.get("kind") == "objective"}
        assert stale in facts and replayed in facts                     # both values recorded, exactly as before
        assert stale not in settlement._signed_realizations(journal)
        assert replayed not in settlement._signed_realizations(journal)
        [row] = [r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict"]
        assert sorted(r["realized"] for r in row["reports"]) == [PROMISED - 2, PROMISED, PROMISED]
        assert not any(r["eligible_to_accept"] for r in row["reports"]) and row["resolvable_now"] is False
        with pytest.raises(ValueError, match="verified founder-signed"):
            settlement.record_resolution(journal, receipt=record.hash, resolves=[e.event_id for e in facts.values()],
                                         accept=facts[stale].event_id, note="stale", command_digest="sha256:x")
        # positive control: the same crafting with a fresh envelope and nonce does verify, so the two above fail on
        # staleness and the replayed nonce, not on how the test built them
        fresh = accepted({"receipt": record.hash, "realized": PROMISED, "source": "external_record", "note": "fresh"})
        assert fresh in settlement._signed_realizations(journal)
