"""Each safeguard of the revoked-device policy (founder policy 2026-11-11) must fail a behavioral test when removed.

    python scripts/ci/check_revoked_device_mutants.py

"Revoking a device should immediately invalidate its unused authority to authorize future execution. Actions already
legitimately completed must remain in the evidence ledger. ... A suspected key compromise should trigger a separate
retrospective integrity review. Distinguish historical validity of a signature from its continuing authority to
approve a new effect."

Mutants are applied in a scratch copy of the repository, never to the working tree; the copy runs without bytecode
and its __pycache__ is purged before each mutant. A mutant is caught only when
tests/unit/test_greg_revoked_device_authority.py reports a FAILED test (an import or collection error does not
count). Exit status 1 if any mutant survives or no longer applies.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_greg_revoked_device_authority.py"
# (what the mutant removes, target file, text found exactly once, its replacement): scripts/repo_review.py reads
# each target and the text after it to check that the anchor still exists.
MUTANTS = [
    # the rule, in the mission fold: unused authority of a revoked device key authorizes nothing
    ("the fold ignores a device revocation", "greg/missions.py",
     '        if kind == "device.revoked":\n            self._revoked(data, event_id)\n            return\n', ''),
    ("a replay-only book does not read who signed an answer", "greg/missions.py",
     '            elif data.get("kind") == "DECISION" and isinstance(data.get("digest"), str):', '            elif False:'),
    ("the verified fold does not keep who signed an answer", "greg/missions.py",
     '        self._signer_of[digest] = ((cmd.get("envelope") or {}).get("founder_key_id"), '
     'str(cmd.get("principal") or ""))', '        pass'),
    ("a voided approval keeps its scope in the mission", "greg/missions.py",
     '                m.approved_scopes.discard(request.get("scope_digest"))', '                pass'),
    ("a voided request is not used up", "greg/missions.py",
     '            self.consumed.add(rid)           # the same scope returning is a new request, never this answer again',
     '            pass'),
    ("a voided request is not withdrawn", "greg/missions.py",
     '            self.withdrawn[rid] = record     # every reader that honours a withdrawal honours this one',
     '            pass'),
    ("a founder-key answer is voided by a revocation record naming its key", "greg/missions.py",
     'if key != kid or not principal.startswith("device:") or rid in self.voided:',
     'if key != kid or rid in self.voided:'),
    ("a revocation voids every device's answers", "greg/missions.py",
     'if key != kid or not principal.startswith("device:") or rid in self.voided:',
     'if not principal.startswith("device:") or rid in self.voided:'),
    # what was used stays: only unused authority is voided
    ("a paid approval whose one run happened is voided", "greg/missions.py",
     'if kind in GATE_SCOPE_ASKS and given == "approve" and not consumed:',
     'if kind in GATE_SCOPE_ASKS and given == "approve":'),
    ("a rejection is voided", "greg/missions.py",
     'if kind in GATE_SCOPE_ASKS and given == "approve" and not consumed:',
     'if kind in GATE_SCOPE_ASKS and not consumed:'),
    ("a sensor-scope approval of a revoked device still admits observations outside the cone", "greg/missions.py",
     'GATE_SCOPE_ASKS = ("APPROVAL", "SENSOR_SCOPE")', 'GATE_SCOPE_ASKS = ("APPROVAL",)'),
    ("an approval of an action is no longer Gate authority to void", "greg/missions.py",
     'GATE_SCOPE_ASKS = ("APPROVAL", "SENSOR_SCOPE")', 'GATE_SCOPE_ASKS = ("SENSOR_SCOPE",)'),
    ("an ask kind is in two revocation classes", "greg/missions.py",
     'NO_AUTHORITY_ASKS = ("NO_STRATEGY", "SENSOR_FAILURE", "COMPUTE", "BODY_AVAILABILITY")',
     'NO_AUTHORITY_ASKS = ("NO_STRATEGY", "SENSOR_FAILURE", "COMPUTE", "BODY_AVAILABILITY", "HUMAN_WORK")'),
    ("an ask kind is in no revocation class", "greg/missions.py",
     'NO_AUTHORITY_ASKS = ("NO_STRATEGY", "SENSOR_FAILURE", "COMPUTE", "BODY_AVAILABILITY")',
     'NO_AUTHORITY_ASKS = ("NO_STRATEGY", "SENSOR_FAILURE", "COMPUTE")'),
    ("a recorded reconciliation is voided", "greg/missions.py",
     'if kind in RECONCILIATION_ASKS and str(given).startswith("reconcile_") and not reconciled:',
     'if kind in RECONCILIATION_ASKS and str(given).startswith("reconcile_"):'),
    ("an unrecorded reconciliation answer of a revoked device still settles", "greg/missions.py",
     'if kind in RECONCILIATION_ASKS and str(given).startswith("reconcile_") and not reconciled:', 'if False:'),
    ("an approval a failed run or a restore already withdrew is voided a second time", "greg/missions.py",
     '                self.consumed.add(data["request_id"])   # used up for every reader',
     '                pass   # used up for every reader'),
    ("a later revocation record of the same key voids the same answer again", "greg/missions.py",
     'if key != kid or not principal.startswith("device:") or rid in self.voided:',
     'if key != kid or not principal.startswith("device:"):'),
    ("the fold forgets which reconciliations were recorded", "greg/missions.py",
     '            if data.get("route") == "founder_reconciliation":', '            if False:'),
    ("a trail record written late takes the scope from an approval given since", "greg/missions.py",
     '                if data["request_id"] not in self.voided:\n'
     '                    m.approved_scopes.discard(request["scope_digest"])',
     '                if True:\n                    m.approved_scopes.discard(request["scope_digest"])'),
    # the engine: a voided reconciliation is asked again before anything else
    ("a live mission may close over a dispatch whose answer was voided", "greg/missions.py",
     '            if reconciling:', '            if False:'),
    ("an ended mission records a voided reconciliation answer", "greg/missions.py",
     '            if (m.blocker or {}).get("type") == "reconciliation" and m.blocker["request_id"] in '
     'self.book.withdrawn:', '            if False:'),
    ("a paused founder is told that a voided approval is about to run", "greg/missions.py",
     '            if b["request_id"] in self.book.withdrawn:   # e.g. its signer device was revoked',
     '            if False:   # e.g. its signer device was revoked'),
    # the body: the revocation command and its trail
    ("a revoked key still signs commands", "greg/body.py",
     '            devices.pop(event.payload["device_key_id"], None)', '            pass'),
    ("a revocation writes no trail", "greg/body.py",
     '            revocation.settle(self.journal, self.engine.book)\n            voided = sorted(',
     '            voided = sorted('),
    ("the turn does not finish a revocation's trail", "greg/body.py",
     '        revocation.settle(self.journal, self.engine.book)\n        if self.paused():', '        if self.paused():'),
    ("a revocation re-sent after a stop is refused instead of finished", "greg/body.py",
     '            if revoked is None:       # else: this very command revoked it before a stop',
     '            if True:       # else: this very command revoked it before a stop'),
    ("a key that is not delegated is revoked", "greg/body.py",
     '                    if marks is None:\n                        raise MissionError("revocation needs',
     '                    if False:\n                        raise MissionError("revocation needs'),
    ("the revocation record drops the suspected-compromise mark", "greg/body.py",
     '                    **({revocation.SUSPECTED: True} if suspected else {}),\n', ''),
    # a suspicion that arises after the key was revoked
    ("a suspicion after a plain revocation is refused", "greg/body.py",
     'marks = revocation.unreviewed_revocation(self.journal, kid) if suspected else None', 'marks = None'),
    ("a plain revocation of an already revoked key is accepted", "greg/body.py",
     'marks = revocation.unreviewed_revocation(self.journal, kid) if suspected else None',
     'marks = revocation.unreviewed_revocation(self.journal, kid)'),
    ("a second suspicion opens a second review of the same revocation", "greg/revocation.py",
     '    return ended if ended is not None and not reviewed else None', '    return ended'),
    ("a review opened under an earlier delegation blocks the review of a later revocation", "greg/revocation.py",
     '        if e.type == "greg.device.enrolled":\n            ended, reviewed = None, False',
     '        if e.type == "greg.device.enrolled":\n            ended = None'),
    ("the review of a late suspicion forgets what the marked revocation voided", "greg/revocation.py",
     '    return {revoked.event_id, revoked.payload.get("marks_revocation")} - {None}',
     '    return {revoked.event_id}'),
    ("the record of a late suspicion does not name the revocation it marks", "greg/body.py",
     '                    **({"marks_revocation": marks} if marks else {})}, key=[kid, digest])',
     '                    }, key=[kid, digest])'),
    ("two revocations of one key share one review", "greg/revocation.py",
     '                                    "revocation": revoked.event_id})[7:31]', '                                    })[7:31]'),
    ("the command result names no review", "greg/body.py",
     '**({"integrity_review": revocation.review_id(revoked)} if suspected else {})}', '}'),
    ("the trail is rewritten over another withdrawal of the same request", "greg/revocation.py",
     '        if book.withdrawn.get(rid) != void:\n            continue', '        if False:\n            continue'),
    ("the trail is recorded again on every turn", "greg/revocation.py",
     '        if journal.retained("decision.withdrawn", key) is None:', '        if True:'),
    ("the review is asked again on every turn", "greg/revocation.py",
     '        if journal.retained("decision.requested", rid) is None:', '        if True:'),
    ("a review reading that fails stops the body", "greg/revocation.py",
     '                review = unbuilt_review(revoked, exc)', '                raise'),
    # the revocation body
    ("the revocation body takes unknown fields", "greg/revocation.py",
     'if not isinstance(body, dict) or set(body) - {"device_key_id", SUSPECTED} or "device_key_id" not in body:',
     'if not isinstance(body, dict) or "device_key_id" not in body:'),
    ("the revoked key id may be something other than text", "greg/revocation.py",
     '    if not isinstance(body["device_key_id"], str):\n', '    if False:\n'),
    ("suspected_compromise takes any value", "greg/revocation.py",
     '    if SUSPECTED in body and body[SUSPECTED] is not True:\n', '    if False:\n'),
    # the retrospective review
    ("a plain revocation opens a review", "greg/revocation.py",
     '        if revoked.payload.get(SUSPECTED) is not True:\n            continue\n        rid = review_id(revoked)',
     '        rid = review_id(revoked)'),
    ("the review lists another signer's commands", "greg/revocation.py",
     'if e.payload.get("founder_key_id") == kid\n                and str(e.payload.get("signer") or "")',
     'if str(e.payload.get("signer") or "")'),
    ("the review reads the ledger past the revocation", "greg/revocation.py",
     'if self._pos.get(e.event_id, 1 << 60) <= self._through]', 'if True]'),
    ("the review misses a dispatch the mission had not recorded when the key was revoked", "greg/revocation.py",
     '                    if g.get("scope_digest") == request.get("scope_digest") and r.seq > seq[event.event_id] \\',
     '                    if False and r.seq > seq[event.event_id] \\'),
    ("the review lists a recorded action a second time as an unrecorded grant", "greg/revocation.py",
     '                            and g.get("grant_id") not in recorded:', '                            and True:'),
    ("the review misses an observation read under a sensor-scope approval", "greg/revocation.py",
     '                        if grant_id in scoped:', '                        if False:'),
    ("the review says a listed signature does not verify", "greg/revocation.py",
     '        return False\n    return True\n', '        return False\n    return False\n'),
    ("the status shows a review for a plain revocation", "greg/revocation.py",
     '        if p.get(SUSPECTED) is True:\n            rid = review_id(revoked)\n            row["integrity_review"]',
     '        if True:\n            rid = review_id(revoked)\n            row["integrity_review"]'),
    ("the status does not say what a revoked key resumed that still runs", "greg/revocation.py",
     '            row["resumed_and_still_running"] = running[p["device_key_id"]]', '            pass'),
    ("the status lists a resume that lifted no pause", "greg/revocation.py",
     'if state == "ACTIVE" and mid in paused else None', 'if state == "ACTIVE" else None'),
    ("the status lists an ended mission as still running", "greg/revocation.py",
     '        if digest in signer and m is not None and m.status not in TERMINAL:',
     '        if digest in signer and m is not None:'),
    ("the status lists the body as resumed by a key that did not resume it", "greg/revocation.py",
     'state[-1].payload.get("command_digest") in signer:', 'True:'),
    ("the CLI signs every revocation as a suspected compromise", "greg/cli.py",
     '                                                   if args.suspected_compromise else {})}, args))',
     '                                                   if True else {})}, args))'),
    ("a goal's evidence does not say that an answer was voided", "greg/goal_gravity.py",
     '**({"answer_voided": book.voided[rid]["why"]} if rid in book.voided else {})}', '}'),
    ("a device answers a review", "greg/missions.py",
     '        if request["kind"] in asks.FOUNDER_KEY_ANSWERS and signer != "founder":', '        if False:'),
    ("the body passes no signer to the answer path", "greg/body.py",
     'self.engine.answer(body, digest, signer=principal)', 'self.engine.answer(body, digest)'),
    ("the fold counts a device's answer to a review", "greg/missions.py",
     '        if request.get("kind") in asks.FOUNDER_KEY_ANSWERS and cmd.get("principal") != "founder":',
     '        if False:'),
    ("a device is offered an answer to a review", "greg/asks.py",
     'if r.get("kind") in FOUNDER_KEY_ANSWERS else r for r in shown]', 'if False else r for r in shown]'),
    ("the phone channel offers a device the review's answer", "greg/remote.py",
     '        full["decisions_required"] = asks.for_signer(full["decisions_required"], principal)\n', ''),
    # the separate appraiser re-derives the rule
    ("the appraiser accepts an act dispatched on a voided approval", "greg/appraisal.py",
     '                    if not _approval_in_force(journal, ledger, seq, requests, answers, '
     'action.get("scope_digest"),',
     '                    if False and not _approval_in_force(journal, ledger, seq, requests, answers, '
     'action.get("scope_digest"),'),
    ("the appraiser voids an approval for a revocation after its dispatch", "greg/appraisal.py",
     'and answer_seq < seq.get(e.event_id, -1) < dispatched_seq for e in journal.replay("device."))',
     'and answer_seq < seq.get(e.event_id, -1) for e in journal.replay("device."))'),
    ("the appraiser places a dispatch at its late record, not at the Gate's grant", "greg/appraisal.py",
     'at_seq, grant_seq.get(grant_id, at_seq)):', 'at_seq, at_seq):'),
    ("the appraiser places a dispatch reconciled as executed at its late record", "greg/appraisal.py",
     '                    grant_id = receipt.payload.get("grant_id") if receipt is not None else \\\n'
     '                        uncertain_grant.get((action["action_id"], action.get("attempt")))',
     '                    grant_id = receipt.payload.get("grant_id") if receipt is not None else None'),
    ("the appraiser voids a founder-key approval", "greg/appraisal.py",
     '    if kid is None or kid in _founder_keys(journal, answer_seq, ledger):\n        return False\n',
     '    if kid is None:\n        return False\n'),
]


def main() -> int:
    return run([(target, name, old, new) for name, target, old, new in MUTANTS], TESTS,
               prefix="revoked-device-mutants-", root=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
