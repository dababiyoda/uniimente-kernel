import io
import json
import time
import unittest

from foundry.http import DEFAULT_PATH, FoundryWSGIApp, MAX_BODY_BYTES
from foundry.transport import (
    ReplayGuard,
    build_signed_headers,
    verify_signed_headers,
)
from provenance.ledger import EvidenceLedger

KEY = "test-interorgan-key"


def underwriting(**overrides):
    payload = {
        "schema_version": "0.1",
        "source_organ": "WealthMachineIntelligence",
        "opportunity_packet_id": "packet-1",
        "packet_digest": "sha256:" + "a" * 64,
        "assessment_id": "assessment-1",
        "assessment_digest": "sha256:" + "b" * 64,
        "observed_pain": "proof is unreliable",
        "core_thesis": "verified proof may reduce disputes",
        "go_no_go": "go",
        "risk_level": "medium",
        "legal_readiness": "standard",
        "evidence_refs": ["sha256:" + "c" * 64],
        "buyer": "Named Buyer LLC",
        "beneficiary": "operations team",
        "pain_owner": "VP Operations",
        "budget_owner": "CFO",
        "recurring_transaction": "approve and settle verified service",
        "trapped_value_usd": 50000,
        "accepted_artifact": "signed verification receipt",
        "external_consequence": "buyer changes settlement decision",
        "lawful_path": "paid diagnostic under reviewed agreement",
        "legal_operator": "alfonso_lopez",
        "missing_fields": [],
        "blocking_reasons": [],
        "ready_for_foundry": True,
        "requires_human_approval": True,
        "execution_authority": "none",
    }
    payload.update(overrides)
    return payload


def request_headers(body, *, idempotency="foundry:packet-1", nonce=None):
    return build_signed_headers(
        body,
        key=KEY,
        identity="wealthmachine",
        schema_version="1.1",
        idempotency_key=idempotency,
        trace_id="packet-1",
        timestamp=str(int(time.time())),
        nonce=nonce,
    )


def invoke(app, body, headers, *, path=DEFAULT_PATH, method="POST", content_length=None):
    environ = {
        "PATH_INFO": path,
        "REQUEST_METHOD": method,
        "CONTENT_LENGTH": str(len(body) if content_length is None else content_length),
        "wsgi.input": io.BytesIO(body),
    }
    for name, value in headers.items():
        environ["HTTP_" + name.upper().replace("-", "_")] = value
    captured = {}

    def start_response(status, response_headers):
        captured["status"] = status
        captured["headers"] = dict(response_headers)

    response_body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], response_body


class FoundryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.ledger = EvidenceLedger("sha256:" + "0" * 64)
        self.app = FoundryWSGIApp(key=KEY, ledger=self.ledger)

    def test_signed_underwriting_is_accepted_but_not_authorized(self):
        body = json.dumps(underwriting(), sort_keys=True).encode()
        status, headers, response_body = invoke(self.app, body, request_headers(body))
        self.assertEqual(status, "202 Accepted")
        payload = json.loads(response_body)
        self.assertEqual(payload["status"], "accepted_for_foundry_analysis")
        self.assertEqual(payload["execution_authority"], "none")
        self.assertTrue(payload["requires_human_approval"])

        receipt = verify_signed_headers(
            headers,
            response_body,
            key=KEY,
            replay_guard=ReplayGuard(),
        )
        self.assertEqual(receipt.identity, "uniimente-kernel")
        self.assertTrue(self.ledger.verify_chain()[0])

    def test_same_idempotent_body_is_returned_as_duplicate(self):
        body = json.dumps(underwriting(), sort_keys=True).encode()
        first = invoke(
            self.app,
            body,
            request_headers(body, idempotency="same", nonce="1" * 32),
        )
        second = invoke(
            self.app,
            body,
            request_headers(body, idempotency="same", nonce="2" * 32),
        )
        self.assertEqual(first[0], "202 Accepted")
        self.assertEqual(second[0], "202 Accepted")
        self.assertFalse(json.loads(first[2])["duplicate"])
        self.assertTrue(json.loads(second[2])["duplicate"])

    def test_nonce_replay_and_changed_content_idempotency_fail_closed(self):
        body = json.dumps(underwriting(), sort_keys=True).encode()
        headers = request_headers(body, idempotency="replay", nonce="3" * 32)
        self.assertEqual(invoke(self.app, body, headers)[0], "202 Accepted")
        self.assertEqual(invoke(self.app, body, headers)[0], "401 Unauthorized")

        changed = json.dumps(underwriting(buyer="Substituted Buyer"), sort_keys=True).encode()
        changed_headers = request_headers(
            changed,
            idempotency="replay",
            nonce="4" * 32,
        )
        self.assertEqual(
            invoke(self.app, changed, changed_headers)[0],
            "401 Unauthorized",
        )

    def test_valid_signature_cannot_widen_execution_authority(self):
        body = json.dumps(underwriting(execution_authority="launch"), sort_keys=True).encode()
        status, _, response_body = invoke(
            self.app,
            body,
            request_headers(body, idempotency="authority"),
        )
        self.assertEqual(status, "422 Unprocessable Entity")
        self.assertIn("zero execution authority", json.loads(response_body)["detail"])

    def test_bad_signature_and_oversized_body_are_rejected(self):
        body = json.dumps(underwriting(), sort_keys=True).encode()
        headers = request_headers(body, idempotency="bad-signature")
        headers["X-Signature"] = "0" * 64
        self.assertEqual(invoke(self.app, body, headers)[0], "401 Unauthorized")
        self.assertEqual(
            invoke(
                self.app,
                b"{}",
                {},
                content_length=MAX_BODY_BYTES + 1,
            )[0],
            "413 Payload Too Large",
        )


if __name__ == "__main__":
    unittest.main()
