"""Selective-disclosure evidence packages for accountable external use (directive section 9).

A package lets GREG show an outside actor (a regulator, a counterparty, a court clerk, a customer) what
its receipts say, revealing only the fields the founder chooses, while the recipient can still check that
every revealed value matches a commitment in the package. It answers "is this what the package committed
to?". It does not answer "did GREG issue this?" (it is unsigned), "is this in GREG's ledger?", "is this
true?", "was this lawful?" or "must we accept it?".

Mechanism: the salted-hash disclosures of RFC 9901 (Selective Disclosure for JSON Web Tokens, IETF
Proposed Standard, November 2025), used without the JWT envelope because GREG holds no issuer signing key
of its own. Each receipt field becomes the disclosure ``base64url(json([salt, name, value]))``, and the
package commits to ``base64url(sha256(disclosure))``. Salts carry 128 random bits, and decoy digests hide
how many fields were withheld, as the RFC recommends. The digest rule is checked against the RFC's own
worked example in the tests.

What a package commits to, and how it can be checked:

* Every receipt asked for. Every other retained receipt with the same input is also included, so one
  answer cannot be presented while a disagreeing one is hidden. Disagreements are flagged without
  revealing their values.
* Custody: each item's ledger record hash and sequence number, the ledger head, the chain verification
  result at packaging time, and the RFC 3161 anchoring state. Inclusion is not checkable from the package:
  GREG's ledger is a linear hash chain whose record hashes cover whole payloads, so showing that a record
  is in it takes the ledger records themselves, which is full disclosure. A witness bundle
  (``greg anchor export``) adds only that a presented ledger was not rewritten after anchoring.
* A requested remedy, labelled as a request. An authorized-action reference must resolve to a retained
  ledger record; nothing else is accepted.
* An institution's response (accepted, disputed, declined) is appended to the journal as its own record.
  The package is never edited, and the response creates no authority.

The package is unsigned: GREG holds no issuer key of its own. A recipient can therefore check that the
revealed values match the package's commitments, but not, cryptographically, that GREG issued it; that rests
on the channel the presentation arrived through. The holder file keeps every disclosure, salts included, and
stays with the body. Only a presentation built from it is shared.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timezone

from provenance.ledger import sha256_json

from .contracts import CognitionError

VERSION = "greg-evidence-package/1"
SALT_BYTES = 16                      # 128 bits, the RFC 9901 recommendation
# Summary fields a recipient needs to read the claim's type, status and limits. Everything else, from
# the problem id and inputs to outputs, proof artifacts and evidence pointers, is withheld unless revealed.
DEFAULT_REVEAL = ("schema_version", "policy_version", "method", "method_version", "epistemic_class", "proof_type",
                  "formal_validity", "abstention_state", "outcome_state", "reason_code", "evaluator",
                  "evaluator_result", "strongest_counterargument", "falsification_condition",
                  "missing_information", "assumptions", "uncertainty", "consequence_class", "authority_created")
DISAGREEMENT_FIELDS = ("output", "abstention_state", "formal_validity")
RESPONSES = ("accepted", "partially_accepted", "disputed", "declined", "no_response")
GROUNDS = ("data", "model", "jurisdiction", "completeness", "relevance", "other")
ACTION_RECORD_TYPES = ("decision", "witness", "event")
LIMITATIONS = (
    "Integrity only: each revealed value matches a commitment in this package. The package is unsigned (GREG "
    "holds no issuer key), so that GREG issued it rests on the channel it arrived through.",
    "Not factual truth: computation and formal validity hold within the encoded model and stated assumptions.",
    "Not legitimacy: no law, consent, rights or authority question is settled by this package.",
    "Not inclusion proof: showing a record is in GREG's ledger takes the ledger records themselves; a witness "
    "bundle only shows that a presented ledger was not rewritten after anchoring.",
    "Not acceptance: the recipient may dispute the data, model, jurisdiction, completeness or relevance, "
    "or decline; its response is recorded, never presumed.")


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def disclosure(name: str, value, salt: str | None = None) -> str:
    """RFC 9901 object-property disclosure: base64url of the JSON array [salt, name, value]."""
    salt = salt or _b64(secrets.token_bytes(SALT_BYTES))
    return _b64(json.dumps([salt, name, value], separators=(",", ":"), sort_keys=True).encode("utf-8"))


def disclosure_digest(text: str) -> str:
    return _b64(hashlib.sha256(text.encode("ascii")).digest())


def _receipt(record):
    from .settlement import _valid_receipt
    output = (record.payload.get("result") or {}).get("output") if record.record_type == "receipt" else None
    return output if _valid_receipt(output) else None


def receipts_for_mission(journal, mission_id: str) -> list[str]:
    """Ledger hashes of the cognitive receipts a mission's observations retained, oldest first."""
    seen = []
    for event in journal.replay("mission.observed"):
        ref = event.payload.get("receipt")
        if event.payload.get("mission_id") == mission_id and ref and ref not in seen:
            record = journal.ledger.find(ref)
            if record is not None and _receipt(record) is not None:
                seen.append(ref)
    return seen


def build_package(journal, receipt_refs, *, recipient: str, purpose: str, requested_remedy: str | None = None,
                  authorized_action_ref: str | None = None, reveal=(), withhold=(), decoys: int = 2,
                  now: datetime | None = None) -> dict:
    """Commit to the receipts (and every same-input receipt), returning the holder file.

    The holder file holds every disclosure and must stay with the body; `present` builds what is shared.
    """
    if not isinstance(recipient, str) or not recipient.strip() or not isinstance(purpose, str) or not purpose.strip():
        raise CognitionError("a package names its recipient and purpose")
    if not 0 <= int(decoys) <= 8:
        raise CognitionError("between 0 and 8 decoy digests per item")
    receipt_refs = list(dict.fromkeys(receipt_refs))
    if not receipt_refs:
        raise CognitionError("name at least one retained cognitive receipt")
    intact, chain_message = journal.ledger.verify_chain()
    if not intact:
        raise CognitionError(f"ledger chain does not verify ({chain_message}); no package is issued from it")
    requested = []
    for ref in receipt_refs:
        record = journal.ledger.find(ref)
        if record is None or _receipt(record) is None:
            raise CognitionError(f"{ref} is not a retained, valid cognitive receipt")
        requested.append(record)
    # Completeness: every retained receipt over the same input travels with the requested ones.
    inputs = {_receipt(r)["input_digest"] for r in requested}
    related = [r for r in journal.ledger.by_type("receipt")
               if r.hash not in receipt_refs and (_receipt(r) or {}).get("input_digest") in inputs]
    items, holder = [], []
    for role, record in [("requested", r) for r in requested] + [("same_input", r) for r in related]:
        receipt = _receipt(record)
        fields = {name: disclosure(name, value) for name, value in sorted(receipt.items())}
        digests = sorted([disclosure_digest(d) for d in fields.values()] +
                         [_b64(hashlib.sha256(secrets.token_bytes(32)).digest()) for _ in range(int(decoys))])
        items.append({"role": role, "receipt_record": record.hash, "seq": record.seq, "digests": digests})
        holder.append({"fields": fields, "input_digest": receipt["input_digest"],
                       "compare": {k: sha256_json(receipt.get(k)) for k in DISAGREEMENT_FIELDS}})
    contradictions = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if holder[i]["input_digest"] == holder[j]["input_digest"]:
                differ = [k for k in DISAGREEMENT_FIELDS if holder[i]["compare"][k] != holder[j]["compare"][k]]
                if differ:
                    contradictions.append({"items": [i, j], "disagree_on": differ,
                                           "note": "same input, different result; values follow the items' disclosure"})
    action = None
    if authorized_action_ref is not None:
        record = journal.ledger.find(authorized_action_ref)
        if record is None or record.record_type not in ACTION_RECORD_TYPES:
            raise CognitionError("an authorized-action reference must be a retained decision, witness or event record")
        action = {"ref": record.hash, "record_type": record.record_type, "seq": record.seq,
                  "note": "a pointer to GREG's own record of the authorization; this package grants nothing"}
    from greg import anchor
    anchoring = anchor.summary(journal)
    package = {
        "version": VERSION, "created_at": (now or datetime.now(timezone.utc)).isoformat(),
        "recipient": recipient.strip(), "purpose": purpose.strip(), "items": items,
        "contradictions": contradictions,
        "custody": {"ledger_head": journal.ledger.head, "records": len(journal.ledger.records),
                    "chain_verified_at_packaging": chain_message,
                    "anchoring": {k: anchoring[k] for k in ("configured", "anchors", "verified", "latest_gen_time")},
                    "inclusion": "not checkable from this package: the ledger is a linear hash chain whose record "
                                 "hashes cover whole payloads, so membership is shown only with the ledger records "
                                 "themselves; a witness bundle from `greg anchor export` then shows that ledger was "
                                 "not rewritten after anchoring"},
        "requested_remedy": None if requested_remedy is None else
            {"text": str(requested_remedy), "status": "requested by the issuer; not a finding"},
        "authorized_action_record": action or
            {"ref": None, "note": "no consequential action is authorized by or recorded in this package"},
        "limitations": list(LIMITATIONS), "authority_created": False,
        "mechanism": "RFC 9901 salted-hash disclosures (SHA-256, 128-bit salts, decoy digests), no JWT envelope"}
    reveal_set = (set(DEFAULT_REVEAL) | set(reveal)) - set(withhold)
    return {"package": package, "package_digest": sha256_json(package), "default_reveal": sorted(reveal_set),
            "disclosures": [h["fields"] for h in holder],
            "custody_note": "holder file: keep with the body; share only a presentation"}


def present(holder: dict, reveal=None) -> dict:
    """The shareable view: the committed package plus the disclosures chosen for revelation."""
    names = set(holder["default_reveal"] if reveal is None else reveal)
    revealed = [[d for name, d in sorted(fields.items()) if name in names] for fields in holder["disclosures"]]
    return {"package": holder["package"], "package_digest": holder["package_digest"], "revealed": revealed}


def verify_presentation(presentation: dict) -> dict:
    """Recipient side, with no access to GREG: do the revealed values match GREG's commitments?"""
    problems, revealed = [], []
    if not isinstance(presentation, dict):
        return {"valid": False, "problems": ["a presentation is a JSON object"], "items": [], "contradictions": [],
                "proves": "nothing", "does_not_prove": list(LIMITATIONS)}
    package = presentation.get("package")
    if not isinstance(package, dict) or sha256_json(package) != presentation.get("package_digest"):
        problems.append("package digest does not match the package")
        package = package if isinstance(package, dict) else {"items": []}
    items = package.get("items", [])
    shown = presentation.get("revealed", [])
    if not isinstance(items, list) or not isinstance(shown, list) or not all(isinstance(d, list) for d in shown):
        problems.append("items and revealed disclosures must be lists")
        items, shown = [], []
    if len(shown) != len(items):
        problems.append("revealed disclosures do not line up with the package items")
    for index, (item, disclosures) in enumerate(zip(items, shown)):
        values, names = {}, set()
        for text in disclosures:
            try:
                salt, name, value = json.loads(_unb64(text))
                salt_ok = len(_unb64(salt)) >= SALT_BYTES
            except (ValueError, TypeError):
                problems.append(f"item {index}: undecodable disclosure")
                continue
            if not salt_ok:
                problems.append(f"item {index}: {name} has a salt under 128 bits")
            elif disclosure_digest(text) not in item.get("digests", []):
                problems.append(f"item {index}: {name} was not committed in this package")
            elif name in names:
                problems.append(f"item {index}: {name} revealed twice")
            else:
                names.add(name)
                values[name] = value
        revealed.append({"revealed": values, "withheld_or_decoy": len(item.get("digests", [])) - len(values)})
    return {"valid": not problems, "problems": problems, "items": revealed,
            "contradictions": package.get("contradictions", []),
            "proves": "the revealed values match the commitments in this package",
            "does_not_prove": list(LIMITATIONS)}


def record_response(journal, package_digest: str, *, actor: str, response: str, scope: str, reported_by: str,
                    grounds=(), evidence_ref: str | None = None, note: str = ""):
    """Append an institution's response to a package. Nothing is rewritten; nothing is authorized."""
    if response not in RESPONSES:
        raise CognitionError(f"response must be one of {RESPONSES}")
    grounds = list(dict.fromkeys(grounds))
    if set(grounds) - set(GROUNDS):
        raise CognitionError(f"grounds must come from {GROUNDS}")
    if response in ("disputed", "declined", "partially_accepted") and not grounds and not note:
        raise CognitionError("a dispute, decline or partial acceptance records its grounds or a note")
    if not all(isinstance(x, str) and x.strip() for x in (package_digest, actor, scope, reported_by)):
        raise CognitionError("package digest, responding actor, scope and reporter are required")
    if evidence_ref is not None and journal.ledger.find(evidence_ref) is None:
        raise CognitionError("an evidence reference must be a retained ledger record")
    payload = {"package_digest": package_digest, "actor": actor, "response": response, "grounds": grounds,
               "scope": scope, "reported_by": reported_by, "evidence_ref": evidence_ref, "note": note[:2000],
               "status": "reported; the response is the actor's, verified only as far as evidence_ref shows",
               "authority_created": False}
    return journal.record("disclosure.response", payload, key=["disclosure.response", package_digest, actor, response,
                                                               reported_by, sha256_json(payload)])


def responses(journal, package_digest: str) -> list[dict]:
    return [e.payload for e in journal.replay("disclosure.response") if e.payload.get("package_digest") == package_digest]
