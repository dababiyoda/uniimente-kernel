"""Reviewer's mutants of the revoked-device change that the builder's gate does not list.

    python reviewer_mutants.py <repo root>   (runs scripts/ci/mutation_harness.run over a scratch copy)
"""
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT / "scripts" / "ci"))
from mutation_harness import run  # noqa: E402

TESTS = "tests/unit/test_greg_revoked_device_authority.py"
MUTANTS = [
    ("R1 voiding a device's reconciliation answer also takes the action's approved scope (a founder's too)",
     "greg/missions.py", '            if m is not None and approval:\n', '            if m is not None:\n'),
    ("R3 the appraiser refutes an act because ANOTHER device was revoked between approval and dispatch",
     "greg/appraisal.py",
     'return any(e.type == "greg.device.revoked" and e.payload.get("device_key_id") == kid\n',
     'return any(e.type == "greg.device.revoked"\n'),
    ("R4 the appraiser voids a fresh approval of a re-delegated key for the key's EARLIER revocation",
     "greg/appraisal.py",
     'and answer_seq < seq.get(e.event_id, -1) < dispatched_seq for e in journal.replay("device."))',
     'and seq.get(e.event_id, -1) < dispatched_seq for e in journal.replay("device."))'),
    ("R5 the review attributes actions run after the approval had been withdrawn", "greg/revocation.py",
     '                end = min(withdrawn_at.get(rid, cut), cut)     # the approval stood from its acceptance to here',
     '                end = cut'),
    ("R6 the review misses a compensation dispatched under the device's approval", "greg/revocation.py",
     '                        effects.append({**_action_row(e, "a compensation dispatched under its approval", basis),\n'
     '                                        "original_receipt": p.get("original_receipt")})',
     '                        pass'),
    ("R7 the review misses a dispatch settled by the device's reconciliation answer", "greg/revocation.py",
     '                        effects.append(_action_row(e, "an interrupted dispatch settled by its answer", basis))',
     '                        pass'),
    ("R8 the review misses compensations run after the device ended a mission", "greg/revocation.py",
     '                if applied.payload.get("state") in ("ABANDONED", "SUPERSEDED"):', '                if False:'),
    ("R9 the review misses a strategy excluded by the device's critique", "greg/revocation.py",
     '                if critique.get("critique_id") and e.payload.get("critique_ref") == critique["critique_id"]:',
     '                if False:'),
    ("R10 the review misses a compensation obligation closed by the device's answer", "greg/revocation.py",
     '                        effects.append(_action_row(e, "a compensation obligation closed by its answer", basis))',
     '                        pass'),
    ("R11 the review says an answer an EARLIER revocation voided was voided by this one", "greg/revocation.py",
     '                if void["voided_by"].get("revocation_event") in revocations else', '                if True else'),
    ("R12 the command result lists what OTHER revocations voided", "greg/body.py",
     '                            if v["voided_by"].get("revocation_command") == digest)', '                            if True)'),
    ("R13 the status lists under each revocation what OTHER revocations voided", "greg/revocation.py",
     '                        if v["voided_by"].get("revocation_event") == revoked.event_id)',
     '                        if True)'),
    ("R14 signature_verifies no longer binds the listed digest to the envelope", "greg/revocation.py",
     '"signature_verifies": bool(public) and sha256_json(env) == digest and _verifies(env, public)}',
     '"signature_verifies": bool(public) and _verifies(env, public)}'),
    ("R18 the review lists a reconciliation record a second time as an action under the approval", "greg/revocation.py",
     '                            and p.get("route") not in ("founder_reconciliation", "standing_reconciliation")\n', ''),
    ("R20 the founder is offered no answer to a review either", "greg/asks.py",
     '    if principal == "founder":\n        return shown\n', ''),
    ("R28 the ask carries every row of a long review instead of the first twenty", "greg/revocation.py",
     'for c in review["commands"][:ASK_SHOWN]],', 'for c in review["commands"]],'),
    ("R31 the review reads Gate grants issued after the revocation", "greg/revocation.py",
     '               and r.payload.get("founder_approved_scope") and r.seq < seq[revoked.event_id]]',
     '               and r.payload.get("founder_approved_scope")]'),
    ("R32 a void made by a restore does not name the restore", "greg/missions.py",
     '                              **({"restore_id": data["restore_id"]} if "restore_id" in data else {})},',
     '                              },'),
]

if __name__ == "__main__":
    only = sys.argv[2:]
    chosen = [m for m in MUTANTS if not only or m[0].split()[0] in only]
    raise SystemExit(run([(target, name, old, new) for name, target, old, new in chosen], TESTS,
                         prefix="rdr-mutants-", root=ROOT))
