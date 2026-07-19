"""Tests for the event spine. Stdlib unittest only."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from uniimente_kernel.events import (  # noqa: E402
    EVENT_FIELDS,
    EventSpine,
    EventValidationError,
    validate_event_dict,
)
from uniimente_kernel.ledger import DecisionLedger  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SCHEMA = os.path.join(REPO_ROOT, "contracts", "event.schema.json")

ORG = "spiffe://uniimente.internal/organ/daleobanks"
AGENT = "spiffe://uniimente.internal/organ/daleobanks/agent/publisher"


class TestEmission(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.ledger = DecisionLedger(path=os.path.join(self.dir.name, "events.jsonl"))
        self.spine = EventSpine(self.ledger, source=ORG, actor=AGENT,
                                legal_principal="alfonso-lopez", policy_version="1.0.0")

    def tearDown(self):
        self.dir.cleanup()

    def test_emit_conforms_and_ledgers(self):
        e = self.spine.emit("signal.detected", subject="packet-1",
                            data={"signal_type": "operator_thought"},
                            expected_consequence="assessment requested")
        d = e.to_dict()
        validate_event_dict(d)  # must not raise
        self.assertEqual(d["source"], ORG)
        self.assertEqual(d["policy_version"], "1.0.0")
        self.assertEqual(d["sensitivity"], "internal")
        entries = self.ledger.replay(event="signal.detected")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["payload"]["id"], e.id)

    def test_events_are_hash_chained(self):
        self.spine.emit("signal.detected")
        self.spine.emit("approval.requested")
        self.spine.emit("capability.issued")
        ok, bad = self.ledger.verify_chain()
        self.assertTrue(ok)
        self.assertIsNone(bad)

    def test_causal_chain_walks_to_origin(self):
        a = self.spine.emit("signal.detected")
        b = self.spine.chain("approval.requested", a)
        c = self.spine.chain("capability.issued", b)
        d = self.spine.chain("action.committed", c)
        chain = self.spine.causal_chain(d.id)
        self.assertEqual([x["id"] for x in chain], [a.id, b.id, c.id, d.id])
        self.assertIsNone(chain[0]["causal_parent"])
        self.assertEqual(chain[-1]["causal_parent"], c.id)

    def test_causal_chain_stops_on_gap(self):
        orphan = self.spine.emit("action.refused", causal_parent=None)
        chain = self.spine.causal_chain(orphan.id)
        self.assertEqual(len(chain), 1)

    def test_replay_and_get(self):
        e = self.spine.emit("evidence.verified", evidence_refs=["sha256:" + "a" * 64])
        self.assertEqual(self.spine.get(e.id)["id"], e.id)
        self.assertIsNone(self.spine.get("missing"))
        self.assertEqual(len(self.spine.replay("evidence.verified")), 1)

    def test_bad_sensitivity_rejected_at_construction(self):
        with self.assertRaises(EventValidationError):
            EventSpine(self.ledger, source=ORG, actor=AGENT,
                       legal_principal="x", default_sensitivity="secret")


class TestValidation(unittest.TestCase):
    def _ok(self):
        return {
            "specversion": "1.0",
            "id": "123e4567-e89b-42d3-a456-426614174000",
            "type": "signal.detected",
            "source": ORG,
            "actor": AGENT,
            "legal_principal": "alfonso-lopez",
            "time": "2026-07-19T00:00:00+00:00",
            "sensitivity": "internal",
            "causal_parent": None,
        }

    def test_valid_passes(self):
        self.assertEqual(validate_event_dict(self._ok())["type"], "signal.detected")

    def test_missing_required_rejected(self):
        for key in ("type", "legal_principal", "causal_parent", "sensitivity"):
            d = self._ok(); d.pop(key)
            with self.assertRaises(EventValidationError, msg=key):
                validate_event_dict(d)

    def test_unknown_fields_rejected(self):
        d = self._ok(); d["execute_now"] = True
        with self.assertRaises(EventValidationError):
            validate_event_dict(d)

    def test_bad_type_pattern_rejected(self):
        d = self._ok(); d["type"] = "SignalDetected"
        with self.assertRaises(EventValidationError):
            validate_event_dict(d)

    def test_non_spiffe_identity_rejected(self):
        d = self._ok(); d["actor"] = "daleobanks"
        with self.assertRaises(EventValidationError):
            validate_event_dict(d)

    def test_bad_hash_rejected(self):
        d = self._ok(); d["evidence_refs"] = ["md5:abc"]
        with self.assertRaises(EventValidationError):
            validate_event_dict(d)

    def test_confidence_range_enforced(self):
        d = self._ok(); d["confidence"] = 1.5
        with self.assertRaises(EventValidationError):
            validate_event_dict(d)

    def test_bad_parent_rejected(self):
        d = self._ok(); d["causal_parent"] = "not-a-uuid"
        with self.assertRaises(EventValidationError):
            validate_event_dict(d)


@unittest.skipUnless(os.path.exists(SCHEMA), "schema file present only in the repo tree")
class TestSchemaParity(unittest.TestCase):
    def test_field_sets_match(self):
        with open(SCHEMA) as f:
            schema = json.load(f)
        self.assertEqual(set(schema["properties"]), set(EVENT_FIELDS))
        self.assertEqual(set(schema["required"]),
                         {"specversion", "id", "type", "source", "actor",
                          "legal_principal", "time", "sensitivity", "causal_parent"})


if __name__ == "__main__":
    unittest.main()
