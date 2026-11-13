"""Each safeguard of the revoked-device policy (founder policy 2026-11-11) must fail a behavioral test when removed.

    python scripts/ci/check_revoked_device_mutants.py

"Revoking a device should immediately invalidate its unused authority to authorize future execution. Actions already
legitimately completed must remain in the evidence ledger. ... A suspected key compromise should trigger a separate
retrospective integrity review. Distinguish historical validity of a signature from its continuing authority to
approve a new effect."

REVIEW_MUTANTS are judged by a second test file, tests/unit/test_greg_revoked_device_review.py. They are the
mutants an independent review of the first draft found alive (its R1 to R32, named here by what they remove), and
the safeguards added in answer to that review: what a review attributes to the key, the hold on the compensations
of a mission the revoked key's own command ended, and what the founder is shown of both.

Mutants are applied in a scratch copy of the repository, never to the working tree; the copy runs without bytecode
and its __pycache__ is purged before each mutant. A mutant is caught only when its test file
(tests/unit/test_greg_revoked_device_authority.py for MUTANTS, tests/unit/test_greg_revoked_device_review.py for
REVIEW_MUTANTS) reports a FAILED test; an import or collection error does not count. Both lists always run. Exit
status 1 if any mutant of either survives or no longer applies.

Mutants of this change that are not listed, and why:

- the review not reading the fold's void as a point where an approval stopped standing (``build_review``, the loop
  over ``book.voided``). Equivalent wherever a review is built by a body: ``settle`` writes the void's
  ``decision.withdrawn`` trail before it builds any review, in the same call that follows the revocation or at the
  start of the next turn before any mission step, so no Gate grant lies between the revocation and its trail, and
  the trail gives the same bound. The loop is kept because the fold, not the trail, is the rule.
- the review reading only the Gate grants issued before the reviewed revocation record (the review's reviewer
  mutant R31). The bound no longer exists as a separate line: each approval's grants are bounded by where that
  approval stopped standing, which is never later than the reviewed record ("a grant issued after an approval
  stopped standing is listed as the key's" below removes that bound).
- the review's reviewer mutant R18, which removes only the exclusion of the two reconciliation routes from the
  actions listed under an approval. Equivalent: both routes write their record with ``receipt: None`` and a status
  that is never UNCERTAIN (MissionEngine._record_reconciliation and the standing reconciliation in
  ``_settle_uncertain``), so the condition on the next line excludes it as well. The listed mutant removes both
  conditions; a test could tell them apart only by a reconciliation record with a receipt, which no code writes.
- ``.get`` fallbacks in ``build_review`` for a mission or a hold that is absent. Unreachable from a ledger a body
  wrote: a listed LIFECYCLE command that ended a mission was accepted from this key, so the fold holds that mission
  from this key's revocation, which the review's ledger prefix always contains.
"""
from pathlib import Path

from mutation_harness import run  # scripts/ci/mutation_harness.py: the shared loop

ROOT = Path(__file__).resolve().parents[2]
TESTS = "tests/unit/test_greg_revoked_device_authority.py"
REVIEW_TESTS = "tests/unit/test_greg_revoked_device_review.py"
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
     '                    if g.get("grant_id") not in recorded:', '                    if False:'),
    ("the review lists a recorded action a second time as an unrecorded grant", "greg/revocation.py",
     '                    if g.get("grant_id") not in recorded:', '                    if True:'),
    ("the review misses an observation read under a sensor-scope approval", "greg/revocation.py",
     '                    if p.get("mission_id") == mission_id and grant[e.event_id] in grants:',
     '                    if False:'),
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
    ("the founder is offered no answer to a review either", "greg/asks.py",
     '    if principal == "founder":\n        return shown\n', ''),
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


REVIEW_MUTANTS = [
    # the fold and the appraiser: safeguards the independent review found without a failing test
    ("voiding a device's reconciliation answer also takes the action's approved scope (a founder's too)",
     "greg/missions.py", '            if m is not None and approval:\n', '            if m is not None:\n'),
    ("the appraiser refutes an act because another device was revoked between approval and dispatch",
     "greg/appraisal.py",
     'return any(e.type == "greg.device.revoked" and e.payload.get("device_key_id") == kid\n',
     'return any(e.type == "greg.device.revoked"\n'),
    ("the appraiser voids a fresh approval of a key delegated again for the key's earlier revocation",
     "greg/appraisal.py",
     'and answer_seq < seq.get(e.event_id, -1) < dispatched_seq for e in journal.replay("device."))',
     'and seq.get(e.event_id, -1) < dispatched_seq for e in journal.replay("device."))'),
    ("a void made by a restore does not name the restore", "greg/missions.py",
     '                              **({"restore_id": data["restore_id"]} if "restore_id" in data else {})},',
     '                              },'),
    # the hold: a mission the revoked key's own command ended runs no compensation on that command
    ("a revocation holds nothing of a mission the revoked key ended", "greg/missions.py",
     '            m.compensation_hold = {"device_key_id": kid, "signer": principal, "revocation_event": event_id,\n'
     '                                   "revocation_command": data.get("command_digest"),\n'
     '                                   "lifecycle_command": m.ended_command, "at": data.get("at")}\n',
     '            pass\n'),
    ("the fold does not keep which command ended a mission", "greg/missions.py",
     '                m.ended_command = data.get("command_digest")\n', ''),
    ("the fold does not read who signed a lifecycle command", "greg/missions.py",
     '            if data.get("kind") == "LIFECYCLE" and isinstance(data.get("digest"), str):',
     '            if False:'),
    ("a revocation holds the missions every device ended", "greg/missions.py",
     '            if m.ended_command is None or m.compensation_hold is not None or key != kid \\',
     '            if m.ended_command is None or m.compensation_hold is not None \\'),
    ("a revocation record naming the founder key holds the missions the founder ended", "greg/missions.py",
     '            if m.ended_command is None or m.compensation_hold is not None or key != kid \\\n'
     '                    or not principal.startswith("device:"):',
     '            if m.ended_command is None or m.compensation_hold is not None or key != kid:'),
    ("a later revocation record of the key takes over a hold", "greg/missions.py",
     '            if m.ended_command is None or m.compensation_hold is not None or key != kid \\',
     '            if m.ended_command is None or key != kid \\'),
    ("a held compensation is dispatched without a decision", "greg/missions.py",
     '        if held is not None and scope not in m.approved_scopes:', '        if False:'),
    ("an approval of a held compensation's exact scope does not run it", "greg/missions.py",
     '        if held is not None and scope not in m.approved_scopes:', '        if held is not None:'),
    # the review: only what the key's own approvals authorized
    ("the review attributes what ran after the approval was withdrawn or voided", "greg/revocation.py",
     '                ends = [x for x in stopped.get(rid, []) + [paid_run] if x in pos] + [revoked.event_id]',
     '                ends = [x for x in [paid_run] if x in pos] + [revoked.event_id]'),
    ("the review attributes a later run of a paid approval's scope", "greg/revocation.py",
     '                ends = [x for x in stopped.get(rid, []) + [paid_run] if x in pos] + [revoked.event_id]',
     '                ends = [x for x in stopped.get(rid, []) if x in pos] + [revoked.event_id]'),
    ("a withdrawal of another request ends this approval", "greg/revocation.py",
     '        stopped.setdefault(e.payload.get("request_id"), []).append(e.event_id)',
     '        stopped.setdefault(None, []).append(e.event_id)'),
    ("a grant issued after an approval stopped standing is listed as the key's", "greg/revocation.py",
     'and r.payload.get("scope_digest") == scope and seq[event.event_id] < r.seq < end_seq]',
     'and r.payload.get("scope_digest") == scope and seq[event.event_id] < r.seq]'),
    ("a dispatch granted under the approval and recorded after it stopped standing is missed", "greg/revocation.py",
     '                        grant[e.event_id] in grants if grant[e.event_id] is not None else at < pos[e.event_id] <= end)',
     '                        at < pos[e.event_id] <= end)'),
    ("a record that names no grant is never attributed", "greg/revocation.py",
     '                        grant[e.event_id] in grants if grant[e.event_id] is not None else at < pos[e.event_id] <= end)',
     '                        grant[e.event_id] in grants)'),
    ("a compensation's dispatch is listed a second time as an unrecorded grant", "greg/revocation.py",
     '    grant = {e.event_id: grant_of(e.payload) for e in actions + observed + compensated}',
     '    grant = {e.event_id: grant_of(e.payload) if e not in compensated else None '
     'for e in actions + observed + compensated}'),
    ("an interrupted compensation's grant is not found by its proposal", "greg/revocation.py",
     '        return by_proposal.get(AuthorityOffice.proposal_id(\n'
     '            p.get("scope_digest"), compensation_attempt(p.get("action_id"), p.get("original_receipt"))))',
     '        return None'),
    ("the review misses a compensation dispatched under the device's approval", "greg/revocation.py",
     '                        effects.append({**_action_row(e, "a compensation dispatched under its approval", basis),\n'
     '                                        "original_receipt": p.get("original_receipt")})',
     '                        pass'),
    ("the review lists a reconciliation record a second time as an action under the approval", "greg/revocation.py",
     '                            and p.get("route") not in ("founder_reconciliation", "standing_reconciliation")\n'
     '                            and (p.get("receipt") or p.get("status") == "UNCERTAIN")):',
     '                            ):'),
    ("the review misses a dispatch settled by the device's reconciliation answer", "greg/revocation.py",
     '                        effects.append(_action_row(e, "an interrupted dispatch settled by its answer", basis))',
     '                        pass'),
    ("the review misses a compensation obligation closed by the device's answer", "greg/revocation.py",
     '                        effects.append(_action_row(e, "a compensation obligation closed by its answer", basis))',
     '                        pass'),
    ("the review misses a strategy excluded by the device's critique", "greg/revocation.py",
     '                if critique.get("critique_id") and e.payload.get("critique_ref") == critique["critique_id"]:',
     '                if False:'),
    # the review and the status: a mission the key ended
    ("the review misses the compensations run after the device ended a mission", "greg/revocation.py",
     '                if applied.payload.get("state") in ("ABANDONED", "SUPERSEDED"):', '                if False:'),
    ("the review misses a compensation interrupted after the device ended a mission", "greg/revocation.py",
     '                                and (p.get("receipt") or p.get("status") == "UNCERTAIN")\n'
     '                                and grant_seq.get(',
     '                                and p.get("receipt")\n'
     '                                and grant_seq.get('),
    ("the review lists under the device a compensation another decision ran after its revocation",
     "greg/revocation.py",
     '                    limit = seq.get(hold.get("revocation_event"), seq[revoked.event_id])',
     '                    limit = seq[revoked.event_id]'),
    ("the review does not list a compensation the revocation holds", "greg/revocation.py",
     '                    for owed in owed_compensations(m, actions, compensated):',
     '                    for owed in ():'),
    ("a compensation that has its record is listed as held", "greg/revocation.py",
     '            if s.get("compensate") and s["action_id"] in done and s["action_id"] not in closed]',
     '            if s.get("compensate") and s["action_id"] in done]'),
    ("the status does not say what a revocation holds", "greg/revocation.py",
     '            row["ended_missions_held"] = holding[revoked.event_id]', '            pass'),
    ("the status lists a held mission under another revocation", "greg/revocation.py",
     '            out.setdefault(m.compensation_hold["revocation_event"], []).append(',
     '            out.setdefault(journal.replay("device.revoked")[0].event_id, []).append('),
    ("the status does not name the ask that decides a held compensation", "greg/revocation.py",
     '                        and r.get("action_id") == owed["action_id"] and rid not in book.answers), None)',
     '                        and False), None)'),
    # the review record and its ask
    ("the review says an answer an earlier revocation voided was voided by this one", "greg/revocation.py",
     '                if void["voided_by"].get("revocation_event") in revocations else', '                if True else'),
    ("the command result lists what other revocations voided", "greg/body.py",
     '                            if v["voided_by"].get("revocation_command") == digest)', '                            if True)'),
    ("the status lists under each revocation what other revocations voided", "greg/revocation.py",
     '                        if v["voided_by"].get("revocation_event") == revoked.event_id)',
     '                        if True)'),
    ("signature_verifies no longer binds the listed digest to the envelope", "greg/revocation.py",
     '"signature_verifies": bool(public) and sha256_json(env) == digest and _verifies(env, public)}',
     '"signature_verifies": bool(public) and _verifies(env, public)}'),
    ("the ask carries every row of a long review instead of the first twenty", "greg/revocation.py",
     'for c in review["commands"][:ASK_SHOWN]],', 'for c in review["commands"]],'),
    # a suspected key delegated again
    ("delegating a suspected key again is not said on the result", "greg/body.py",
     '                    **({"warning": revocation.SUSPECTED_AGAIN, "integrity_reviews": suspected} if suspected '
     'else {})}',
     '                    }'),
    ("a key revoked plainly is called suspected when it is delegated again", "greg/revocation.py",
     '            if e.payload.get("device_key_id") == kid and e.payload.get(SUSPECTED) is True]',
     '            if e.payload.get("device_key_id") == kid]'),
    ("another key's suspected revocation is held against a key delegated again", "greg/revocation.py",
     '            if e.payload.get("device_key_id") == kid and e.payload.get(SUSPECTED) is True]',
     '            if e.payload.get(SUSPECTED) is True]'),
    ("the status does not say that a suspected key was delegated again", "greg/revocation.py",
     '            if again:                             # the founder delegated the suspected key again: said, not '
     'refused',
     '            if False:'),
    ("the status counts the delegation that was revoked as a new one", "greg/revocation.py",
     '                     and pos[e.event_id] > pos[revoked.event_id]]', '                     ]'),
]


def main() -> int:
    # Both lists run to the end: a survivor in the first does not hide one in the second.
    codes = [run([(target, name, old, new) for name, target, old, new in mutants], tests,
                 prefix="revoked-device-mutants-", root=ROOT)
             for tests, mutants in ((TESTS, MUTANTS), (REVIEW_TESTS, REVIEW_MUTANTS))]
    return int(any(codes))


if __name__ == "__main__":
    raise SystemExit(main())
