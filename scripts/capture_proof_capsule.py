#!/usr/bin/env python3
"""Capture the WP-03 Proof Capsule: the first verified external consequence.

Runs ONE real external effect through the full UNIIMENTE kernel loop and
seals the evidence:

    compiled constitution (WP-02 policy_fn over the five real .ucl files)
      -> Consequence Gate (WP-01, 15 stages)
      -> C2 research_fetch intent => REQUIRE_HUMAN (doctrine.humans_authorize)
      -> founder approval bound to the exact intent fingerprint
         (in-process key for the proof run; in production this is Alfonso's
         hardware key — see SPEC-WP03 section 7)
      -> one_use grant -> signed CommitWitness -> REAUTHORIZE
      -> HttpResearchAdapter performs ONE real HTTPS GET of
         https://example.com/ (the only network call this script makes)
      -> signed ExecutionReceipt (body never stored — only its sha256)
      -> VERIFY -> RECONCILE -> OUTCOME -> closed DecisionEpisode
      -> every artifact hash-chained on the append-only spine

The capsule (proof/wp03_capsule.json) collects the versions, the intent
fingerprint, the approval/witness/receipt ids, the signed receipt facts
(status, bytes, response hash, final_url), the reconciliation verdict, the
episode closure, the FULL spine record list, and spine.verify_chain().

The approved expected_outcome is a canonical-JSON expectation document
pinning status_code, final_url, and the exact body sha256 of the IANA
example.com page (chosen by SPEC-WP03 because it is IANA-operated and
content-stable). The adapter refuses to attest if the live response
contradicts any pinned value — if IANA ever changes the page, this script
fails closed (exit 1) instead of attesting a different outcome.

Exit code: 0 on success, nonzero on ANY failure (Hard Rule 4).

Usage (from the slice root):  python scripts/capture_proof_capsule.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from kernel.adapters.http_research import (  # noqa: E402
    ADAPTER_ID,
    DEFAULT_ALLOWLIST,
    USER_AGENT,
    HttpResearchAdapter,
    allowlist_version,
)
from kernel.authority.approvals import ApprovalService  # noqa: E402
from kernel.contracts.action import ActionIntent  # noqa: E402
from kernel.crypto.hashing import canonical_json  # noqa: E402
from kernel.gate import errors  # noqa: E402
from kernel.gate.pipeline import Gate  # noqa: E402
from kernel.spine import Spine  # noqa: E402
from kernel.ucl import Constitution, compile_policy_fn  # noqa: E402
from kernel.ucl.version import constitution_version_from_dir, policy_version  # noqa: E402

TARGET_URL = "https://example.com/"
EXPECTED_STATUS = 200
# sha256 of the IANA example.com page body (559 bytes), verified live in the
# build sandbox on 2026-07-20. Pinned so the founder-approved fingerprint
# binds the EXACT expected bytes, not merely "some 200 response".
EXPECTED_BODY_SHA256 = "ff67a9d764d6a2367a187734e697f6a53217db9a21c101d410a113ca871a299d"
CAPSULE_PATH = REPO_ROOT / "proof" / "wp03_capsule.json"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_intent(expected_outcome: str) -> ActionIntent:
    """The golden C2 research_fetch intent (one bounded GET of example.com)."""
    return ActionIntent(
        actor_id="uniimente-kernel",
        organ_id="research-organ",
        legal_principal="Uniimente Ltd",
        objective=(
            "WP-03 proof: close one real external loop — a single bounded "
            "HTTPS GET of https://example.com/ through the Consequence Gate"
        ),
        action_type="research_fetch",
        resource="web",
        target=TARGET_URL,
        payload={"method": "GET", "max_bytes": 262144, "max_redirects": 3},
        consequence_class="C2",
        evidence_ids=[],
        expected_outcome=expected_outcome,
        rollback=None,
        expiry_minutes=30,
    )


def collect_capsule(
    *,
    versions: dict,
    fingerprint: str,
    approval_id: str | None,
    spine: Spine,
    ok: bool,
    error: str | None,
) -> dict:
    """Assemble the capsule from the spine — the single source of truth."""
    records = list(spine.iter())

    def payloads(kind):
        return [r["payload"] for r in records if r["kind"] == kind]

    receipts = payloads("ExecutionReceipt")
    receipt_facts = json.loads(receipts[-1]["external_id"]) if receipts else None
    reconciliations = payloads("ReconciliationRecord")
    episodes = payloads("DecisionEpisode")
    episode = episodes[-1] if episodes else None
    return {
        "capsule_schema": "wp03-proof-capsule/1.0",
        "generated_at": _utcnow_iso(),  # wall clock: capsule metadata only
        "ok": ok,
        "error": error,
        "versions": {
            "policy_version": versions["policy_version"],
            "constitution_version": versions["constitution_version"],
            "adapter_id": ADAPTER_ID,
            "allowlist": list(DEFAULT_ALLOWLIST),
            "allowlist_version": allowlist_version(DEFAULT_ALLOWLIST),
            "user_agent": USER_AGENT,
        },
        "intent_fingerprint": fingerprint,
        "approval_id": approval_id,
        "witness_id": episode["witness_id"] if episode else None,
        "receipt": (
            {
                "receipt_id": receipts[-1]["id"],
                "witness_id": receipts[-1]["witness_id"],
                "adapter_id": receipts[-1]["adapter_id"],
                "provider_response_hash": receipts[-1]["provider_response_hash"],
                "status_code": receipt_facts["status_code"],
                "bytes_fetched": receipt_facts["bytes_fetched"],
                "body_sha256": receipt_facts["body_sha256"],
                "final_url": receipt_facts["final_url"],
                "fetched_at": receipt_facts["fetched_at"],
                "executed_at": receipts[-1]["executed_at"],
                "signature": receipts[-1]["signature"],
            }
            if receipts
            else None
        ),
        "reconciliation": reconciliations[-1] if reconciliations else None,
        "episode": episode,
        "spine_records": records,
        "verify_chain": spine.verify_chain(),
    }


def main() -> int:
    constitution_dir = REPO_ROOT / "constitution"
    model = Constitution.from_directory(constitution_dir, current_state="normal")
    versions = {
        "policy_version": policy_version(model),
        "constitution_version": constitution_version_from_dir(constitution_dir),
    }
    policy_fn = compile_policy_fn(model, **versions)

    # Fresh spine in a temp dir; the capsule carries every record it seals.
    spine = Spine(Path(tempfile.mkdtemp(prefix="wp03-spine-")) / "spine")
    authority = ApprovalService(approver_id="founder")  # fresh founder key
    gate = Gate(
        versions["policy_version"],
        versions["constitution_version"],
        authority,
        spine,
        policy_fn=policy_fn,
    )
    adapter = HttpResearchAdapter(witness_public_key=authority.public_key)
    gate.register_adapter(adapter.adapter_id, adapter.public_key_hex)

    # The approved expectation pins the exact response the founder signs off.
    expected_outcome = canonical_json(
        {
            "body_sha256": EXPECTED_BODY_SHA256,
            "description": "one bounded HTTPS GET of the IANA example.com page",
            "final_url": TARGET_URL,
            "status_code": EXPECTED_STATUS,
        }
    )
    intent = build_intent(expected_outcome)
    fingerprint = gate.fingerprint(intent)
    # Simulating the human: founder approval for the EXACT fingerprint.
    approval = authority.issue_approval(fingerprint)

    ok, error = True, None
    try:
        episode = gate.run(intent, adapter=adapter, approval=approval)
        assert episode.closed and episode.close_reason == "completed"
    except errors.GateRefusal as refusal:
        ok, error = False, str(refusal)

    capsule = collect_capsule(
        versions=versions,
        fingerprint=fingerprint,
        approval_id=approval.id,
        spine=spine,
        ok=ok,
        error=error,
    )
    CAPSULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CAPSULE_PATH.write_text(
        json.dumps(capsule, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    receipt = capsule["receipt"] or {}
    reconciliation = capsule["reconciliation"] or {}
    print(
        "WP-03 PROOF CAPSULE: "
        f"ok={capsule['ok']} "
        f"status={receipt.get('status_code')} "
        f"bytes={receipt.get('bytes_fetched')} "
        f"body_sha256={receipt.get('body_sha256')} "
        f"reconciled={reconciliation.get('reconciled')} "
        f"verify_chain={capsule['verify_chain']} "
        f"records={len(capsule['spine_records'])} "
        f"-> {CAPSULE_PATH.relative_to(REPO_ROOT)}"
    )
    if not capsule["ok"]:
        print(f"REFUSAL: {error}", file=sys.stderr)
    if not (capsule["ok"] and capsule["verify_chain"] and reconciliation.get("reconciled")):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
