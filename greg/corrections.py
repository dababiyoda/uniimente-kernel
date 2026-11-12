"""Evidence-correction propagation: a changed, retracted, expired or contradicted reading marks what rests on it.

Directive section 45 (S45.A3, S43.A4): "track freshness; preserve corrections". The 2026-11-04 re-issue, behaviour B:
"A retracted source, changed API, expired measurement, or failed replication should selectively invalidate dependent
claims or trigger requalification. Preserve historical records and identify decisions requiring review. Grant
revocation is separate: the Kernel must deny affected execution immediately. Epistemic requalification cannot restore
permission."

Nothing here is a second ledger. The dependency index is derived each tick from records the body already keeps:

- a **reading** is a ``mission.observed`` event and its Gate receipt; the receipt's output names the source it read
  (``fs.read`` path and sha256, ``http.get`` url, sha256, final url and status, ``document.text`` path and snapshot
  digest, ``git.inspect`` head, ``browser.render`` DOM digest) and any expiry its evidence carries (``expires_at``);
- a **delivered claim** is a bounded closure (``mission.achieved``), or the latest hold of a standing mission
  (``mission.held``; its earlier holds are superseded by its own re-observation), and the receipts it cites. A standing
  mission's own later readings are its homeostasis, not a correction: only another mission's readings count against
  its hold;
- its **descendants** are the strategy actions that bound one of those receipts (``bindings``, ``input_bindings``),
  the claims of missions that acted on such an action afterwards, the founder asks whose evidence names an affected
  receipt or that approved such an action (its scope digest) and their answers, the settled outcomes on its readings
  (``cognition.settled``) and the procedures proposed from its mission (``sop.proposed``).

A **cause** is found when a later record contradicts a reading a delivered claim rests on (a founder rejection may
also name a reading no closure cites, or one a failure closure rests on):

- SOURCE_CHANGED: the same source read later with a different digest; SOURCE_RETRACTED: read later as absent (a
  missing file, HTTP 404 or 410);
- API_CHANGED: the same URL answering with a different final URL or status class (a server error, 5xx, is not a
  reading of the source at all). A capability later quarantined because its identity changed is not a cause: every
  adapter re-checks its pinned identity before each run, so what it read before was read by what was verified;
- MEASUREMENT_EXPIRED: an ``expires_at`` of an evidence source in one of GREG's own cognition receipts has passed
  (an expiry inside other data, an MCP server's for instance, is that data's, not the measurement's);
- REPLICATION_FAILED: the same signed sensor (instrument, input and predicate) read later fails on the same input
  (the same source digest, or a computation with no source). A later computation that held no answer (a capability
  deficit, a timeout, a stopped worker: ``no_method_ran``) replicates nothing; one that answered and failed the
  check, or REFUTED the claim, is a real negative;
- APPRAISAL_REFUTED: the closure's independent appraisal is REFUTED;
- FOUNDER_REJECTED: a critique the founder signed rejects a reading (``signed_rejections``; a ``critique.recorded``
  row with no accepted signed command behind it is not his word). What a rejection rejects depends on the event it
  names (``Index.rejected_by``): a closure, its cited readings; an appraisal, the closure it judged; a reading or a
  settled outcome, that reading, cited or not; a failure closure (``mission.unmet``), the failing readings it
  closed on. A rejection of any other event names no reading; the command's result says that it changed no credit
  (``rejection_effect``).

Each cause is recorded once (``evidence.invalidated``), with the correction it propagates (``evidence.correction``:
every affected descendant and the edge it was reached by, and how many delivered claims are unaffected). History is
never edited. Only the causes that impugn the measurement itself (replication on the same input, a refuted appraisal,
a founder rejection) touch what was credited on it. A refuted appraisal already does, wherever the appraisal is read.
A failed replication and a founder rejection are seen by no appraisal, so they contain (``containment``): the
settled outcomes on their receipts (``contained_receipts``, read by ``settlement.measured_outcomes``, so by every
reader of settled competence) and their missions as evidence for a procedure or a precedent (``contained_missions``,
read by ``sop.closed_procedures`` and ``precedents``); a founder rejection's missions also stop counting as
successes in routing reliability, the earned-autonomy report and precedent action evidence (``rejected_missions``).
A source that moved on leaves the method that read it as competent as before. What is contained is scored as neither
success nor failure: a contained failure (the founder rejected a failure closure) stops counting against its method
by the same rule.

A founder rejection withholds the answer, not one receipt of it. While it stands, every reading that carries the
rejected answer is contained with it (``Index.same_answer``): an earlier or later reading of the same signed check in
the same mission, a standing mission's own next cadence read, and, for one of GREG's own computations, the same
question (instrument, input, predicate) answered alike by the same method at the same version in another mission.
A reading with a different answer is a new answer and settles on its own merits. A rejection does not reach a
different question, different inputs, another version of the method or an unrelated mission (the founder's decision
of 2026-11-12: "Scope rejection history to the relevant answer, evidence, task conditions, and version").

The founder can requalify what he rejected: a later signed CRITIQUE that accepts the closure, the appraisal, a
reading or the settled outcome of the rejected answer lifts the withholding for that answer and for no other
(``Index.rejections``), from the acceptance of that command on. Propagation records it against the cause, with the
critique and the command it came from. A rejection signed after it stands again. A later passing reading, a critique
row with no accepted signed command behind it and a bare ``evidence.requalified`` record lift nothing. Wherever
credit is withheld the reason is stated: the cause, for a founder rejection the critique and the answer it
withholds, and what lifts it (``_standing``, ``settlement.withheld``, ``rejection_report``).

Containment is derived from the journal each time it is read. A founder rejection counts from the acceptance of
its signed command, before any tick records its cause, and a dependent that appears after a correction was recorded
(a mission that binds a contained reading, a later reading of a rejected answer) is contained when it exists. The
stored ``affected`` list is history and the basis of the ask.

Every cause marks its claims NEEDS_REVIEW and names the decisions to review; a terminal delivery, or one another
mission or a founder decision depended on, is also put to the founder, once per triggering record and mission
(EVIDENCE_CORRECTION, answer only recorded), from the stored correction.

A cause is **requalified** by evidence alone (``evidence.requalified``): a later passing reading of the same signed
sensor, with no expired evidence of its own; a refuted appraisal only by a later
VERIFIED appraisal of the same closure. A founder rejection is never requalified by evidence: only his own signed
acceptance lifts it, and the record of that is derived from the signed critiques, never trusted on its own. The
requalifying reading becomes the
claim's basis, so a later change against it is a new cause. Requalification lifts the epistemic mark only. This
module writes no grant, approval or capability state, so it can neither deny nor restore permission: a detach, a
revoked device or a voided approval keeps denying execution through the Kernel's own path, whatever the evidence
later shows.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json

from greg import asks
from greg.journal import Journal, fact_id, iso
from provenance.ledger import sha256_json

CLASSES = ("SOURCE_CHANGED", "SOURCE_RETRACTED", "API_CHANGED", "MEASUREMENT_EXPIRED", "REPLICATION_FAILED",
           "APPRAISAL_REFUTED", "FOUNDER_REJECTED")
RETRACTED_STATUS = (404, 410)
# Causes whose trigger is itself a record the founder already sees and the machine already acts on: a refuted
# appraisal of the mission's own closure (autonomy, routing and Goal Gravity consume it) and the founder's own
# rejection. They put an ask only when something beyond that mission rests on the claim.
SELF_REPORTED = ("APPRAISAL_REFUTED", "FOUNDER_REJECTED")
# A cause whose credit effect its own readers already have. Settlement and SOP read each closure's appraisal, and a
# later VERIFIED appraisal of that closure restores what a refuted one withdrew; containment adds nothing to it.
APPRAISED = ("APPRAISAL_REFUTED",)
COMPUTATIONS = ("cognition.",)        # sensors whose reading is a computation on its signed input, not the world
# The states of a compilation in which a method ran and said something. REFUTED is a real negative result. Every
# other state (UNKNOWN after a timeout, ABSTAIN after a stopped worker, a deficit, an incomplete formalization, a
# question for a human) holds no answer.
ANSWERED = ("ANSWERED", "WORLD_UNVERIFIED", "REFUTED")
# Fields of a certified answer that say how it was produced, not what it is (``settlement.ANSWER_PROVENANCE_FIELDS``).
ANSWER_PROVENANCE = ("engine", "composed_of", "authority_created")
MAX_DEPTH = 6                          # how deep an output is searched for evidence expiries


# -- what a reading read ------------------------------------------------------------------------------------------

def source_of(output) -> dict | None:
    """The source a receipt output read: {key, digest, absent, api, server_error}; None when it names none.

    One file is one source whatever instrument read it: ``fs.read``'s ``sha256``, ``document.text``'s
    ``input_sha256`` and a complete ``fs.search``'s ``read_sha256`` are each the sha256 of its bytes."""
    if not isinstance(output, dict):
        return None
    if isinstance(output.get("url"), str) and ("sha256" in output or "dom_sha256" in output):
        kind = "sha256" if "sha256" in output else "dom_sha256"
        status = output.get("status")
        return {"key": f"url:{output['url']}#{kind}", "digest": output.get(kind),
                "absent": status in RETRACTED_STATUS, "server_error": isinstance(status, int) and status >= 500,
                "api": [sha256_json({"u": output.get("final_url")})[7:23], status // 100 if isinstance(status, int)
                        else None] if "final_url" in output or "status" in output else None}  # no server text kept
    if isinstance(output.get("path"), str):
        path, out = output["path"], {"absent": False, "server_error": False, "api": None}
        if isinstance(output.get("head"), str):
            return {**out, "key": f"repo:{path}", "digest": output["head"]}
        for field in ("sha256", "input_sha256"):
            if isinstance(output.get(field), str):
                return {**out, "key": f"path:{path}", "digest": output[field]}
        if isinstance(output.get("read_sha256"), str) and output.get("bytes_read") == output.get("size"):
            return {**out, "key": f"path:{path}", "digest": output["read_sha256"]}
        if output.get("exists") is False:
            return {**out, "key": f"path:{path}", "digest": None, "absent": True}
    return None


def expiries(output, depth: int = 0) -> list[str]:
    """The ``expires_at`` of every evidence source (a dict that also names its ``digest``) in a cognition receipt
    output, and its ``evidence_expires_at``. Only GREG's own cognition receipts are read for this (see Index)."""
    found = []
    if depth > MAX_DEPTH:
        return found
    if isinstance(output, dict):
        if depth == 0 and isinstance(output.get("evidence_expires_at"), str):
            found.append(output["evidence_expires_at"])
        if isinstance(output.get("expires_at"), str) and "digest" in output:
            found.append(output["expires_at"])
        for v in output.values():
            if isinstance(v, (dict, list)):
                found += expiries(v, depth + 1)
    elif isinstance(output, list):
        for v in output:
            found += expiries(v, depth + 1)
    return found


def no_method_ran(output) -> bool:
    """A cognition receipt that holds no answer: a compilation that ended in any state but ``ANSWERED`` (a capability
    deficit, a timeout recorded as UNKNOWN, a stopped worker recorded as ABSTAIN, an incomplete formalization), or a
    method receipt that ended in a capability deficit. It neither fails nor replicates a claim another reading
    answered: a host that stalls on a later mission says nothing about the method that answered the first. A
    compilation that answered and failed the check, and one that REFUTED the claim, are real negatives."""
    return isinstance(output, dict) and (output.get("state") not in (None, *ANSWERED)
                                         or output.get("abstention_state") == "CAPABILITY_DEFICIT")


def answered(output) -> str | None:
    """The digest of what one of GREG's own cognition receipts answered: the method that ran, its version and its
    answer. None when it holds no answer. A compilation names the method through the receipt of the method it
    selected; its answer is its ``result`` without the provenance fields. Timing, cost and receipt ids are not part
    of it, so the same answer delivered again under another receipt has the same digest."""
    if not isinstance(output, dict):
        return None
    if "state" in output:
        if output["state"] not in ANSWERED:
            return None
        inner = output.get("selected_receipt") if isinstance(output.get("selected_receipt"), dict) else {}
        result = output.get("result")
        if isinstance(result, dict):
            result = {k: v for k, v in result.items() if k not in ANSWER_PROVENANCE}
        return sha256_json({"method": inner.get("method") or output.get("method_or_composition_selected"),
                            "method_version": inner.get("method_version"), "answer": result})
    if output.get("abstention_state") in ("NONE", "REFUTED", "WORLD_UNVERIFIED"):
        return sha256_json({"method": output.get("method"), "method_version": output.get("method_version"),
                            "answer": output.get("output")})
    return None


def sensor_key(check: dict) -> str:
    """What a signed check asks: its instrument, its input and its predicate. Its label (check id, description) and
    the mission that signed it are not part of the question."""
    s = check.get("sensor") or {}
    return sha256_json({"sensor": s.get("capability") or s.get("function"), "params": s.get("params", {}),
                        "predicate": check.get("predicate")})


def signed_critiques(journal: Journal, verdicts=("reject", "accept")) -> list:
    """The founder's critiques of these verdicts, in ledger order: every ``critique.recorded`` event that an accepted
    signed CRITIQUE command stands behind (a ``command.accepted`` of kind CRITIQUE with the row's command digest,
    whose signed body names the same target and the same verdict). A row with no such command behind it is not the
    founder's word and is not followed, whichever way it points."""
    rows = [e for e in journal.replay("critique.recorded") if e.payload.get("verdict") in verdicts]
    if not rows:
        return []
    from greg.founder import accepted_body         # the body the founder signed, in either retained record shape
    accepted = {e.payload.get("digest"): accepted_body(e.payload) or {}
                for e in journal.replay("command.accepted") if e.payload.get("kind") == "CRITIQUE"}
    out = []
    for e in rows:
        signed = accepted.get(e.payload.get("command_digest")) if e.payload.get("command_digest") else None
        if signed is not None and signed.get("verdict") == e.payload.get("verdict") \
                and signed.get("target_event_id") == e.payload.get("target_event_id"):
            out.append(e)
    return out


def signed_rejections(journal: Journal) -> list:
    """The signed critiques that reject (``signed_critiques``), standing or since requalified."""
    return signed_critiques(journal, ("reject",))


LIFTS = {"FOUNDER_REJECTED": "a founder-signed CRITIQUE that accepts the rejected closure, reading or answer "
                             "(greg accept EVENT_ID); no later reading and no other record lifts it",
         "REPLICATION_FAILED": "a later passing reading of the same signed sensor on the same input"}


def _cause_id(cls: str, root: str, on: str) -> str:
    return "cause-" + sha256_json({"class": cls, "root": root, "on": on})[7:39]


def _instant(text: str) -> datetime | None:
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return value if value.tzinfo else None


# -- the index ----------------------------------------------------------------------------------------------------

class Index:
    """Readings, delivered claims and their descendants, derived from the journal and its ledger."""

    def __init__(self, journal: Journal):
        self.journal, ledger = journal, journal.ledger
        sensors, self.specs = {}, {}
        for e in journal.replay("mission.registered"):
            self.specs[e.payload["mission_id"]] = e.payload["spec"]
            for check in e.payload["spec"].get("success_checks", []):
                sensors[(e.payload["mission_id"], check["check_id"])] = sensor_key(check)
        self.readings, self.by_receipt, self.by_event, self._targets, self._rejections = [], {}, {}, None, None
        for e in journal.replay("mission.observed"):
            p = e.payload
            record = ledger.find(p["receipt"]) if p.get("receipt") else None
            if record is None:
                continue
            output = (record.payload.get("result") or {}).get("output")
            own = str(p.get("capability", "")).startswith("cognition.")     # GREG's own receipts carry evidence
            source = source_of(output)
            reading = {"event_id": e.event_id, "mission_id": p["mission_id"], "check_id": p["check_id"],
                       "receipt": p["receipt"], "seq": record.seq, "capability": p.get("capability"),
                       "passed": bool(p.get("passed")), "inconclusive": str(p.get("detail", "")).startswith("sensor "),
                       "no_method": own and no_method_ran(output), "own": own,
                       # what the reading answered: a computation's method and answer, a world reading's bytes
                       "answer": answered(output) if own else (source or {}).get("digest"),
                       "sensor": sensors.get((p["mission_id"], p["check_id"])), "source": source,
                       "expires": sorted(expiries(output)) if own else [], "at": p.get("at")}
            self.readings.append(reading)
            self.by_receipt[p["receipt"]] = reading
            self.by_event[e.event_id] = reading
        self.head_seq = max((r["seq"] for r in self.readings), default=-1)
        self.claims, latest_hold = [], {}
        for e in journal.replay("mission.held"):
            latest_hold[e.payload["mission_id"]] = e        # earlier holds are superseded by the mission's own
        for kind, events in (("achieved", journal.replay("mission.achieved")), ("held", list(latest_hold.values()))):
            for e in events:
                cited = [r for r in e.payload.get("evidence", []) if r in self.by_receipt]
                self.claims.append({"claim": e.event_id, "kind": kind, "mission_id": e.payload["mission_id"],
                                    "receipts": cited, "seq": max([self.by_receipt[r]["seq"] for r in cited] or [-1]),
                                    "at": e.payload.get("at")})
        self.actions = []
        for e in journal.replay("mission.action"):
            record = ledger.find(e.payload["receipt"]) if e.payload.get("receipt") else None
            if record is not None:
                self.actions.append((e, record.seq))

    def _event_seq(self, event) -> int:
        h = self.journal.event_hash(event.event_id)
        record = self.journal.ledger.find(h) if h else None
        return record.seq if record is not None else -1

    # -- what a founder rejection rejects -----------------------------------------------------------------------
    def identity(self, reading: dict) -> str | None:
        """The answer a reading carries, as one digest: what was asked (the signed sensor: instrument, input,
        predicate) and what was answered (``answered``, or a world reading's bytes). None when either is unknown."""
        if reading["answer"] is None or reading["sensor"] is None:
            return None
        return sha256_json({"asked": reading["sensor"], "answered": reading["answer"]})

    def rejections(self) -> tuple[list, dict]:
        """(standing, lifted) founder rejections, from the signed critiques in ledger order.

        ``standing`` is a list of (critique event, rejected reading). ``lifted`` maps (critique event id, reading
        receipt) to the later signed critique that accepted the same answer: the closure, appraisal, reading or
        settled outcome the acceptance names (``rejected_by``), and every reading that carries the answer of one of
        them (``same_answer``). The acceptance requalifies exactly those answers and nothing else; a rejection
        signed after it stands again. Evidence alone never lifts a rejection, and neither does any other record."""
        if self._rejections is None:
            standing, lifted = {}, {}
            for e in signed_critiques(self.journal):
                readings = self.rejected_by(e.payload.get("target_event_id"))[1]
                if e.payload["verdict"] == "reject":
                    for reading in readings:
                        standing[e.event_id, reading["receipt"]] = (e, reading)
                    continue
                accepted = {r["receipt"] for a in readings for r in (a, *self.same_answer(a))}
                for key in [k for k in standing if k[1] in accepted]:
                    del standing[key]
                    lifted[key] = e
            self._rejections = (list(standing.values()), lifted)
        return self._rejections

    def same_answer(self, reading: dict) -> list[dict]:
        """The other readings that carry this reading's answer: the same signed check of the same mission with the
        same outcome and the same answer digest, whichever receipt each has; and, for one of GREG's own
        computations, the same question (instrument, input and predicate) answered alike by the same method at the
        same version in any mission. A reading that names no answer digest is like no other."""
        if reading["answer"] is None:
            return []
        return [r for r in self.readings
                if r is not reading and r["answer"] == reading["answer"] and r["passed"] == reading["passed"]
                and ((r["mission_id"], r["check_id"]) == (reading["mission_id"], reading["check_id"])
                     or (reading["own"] and r["own"] and r["sensor"] is not None and r["sensor"] == reading["sensor"]))]

    def rejected_by(self, target) -> tuple[str, list[dict]]:
        """(what the event is, the readings a rejection of it rejects).

        A closure (``mission.achieved``, ``mission.held``): the readings it cites. A failure closure
        (``mission.unmet``): the latest reading, before it, of each check it names as failing. A reading
        (``mission.observed``): itself, cited by a closure or not. A settled outcome (``cognition.settled``): the
        reading it settled. An appraisal (``mission.appraised``): what the closure it judged rejects. Any other
        event names no reading of a signed check: ("other", [])."""
        if target in self.by_event:
            return "reading", [self.by_event[target]]
        if self._targets is None:
            self._targets = {e.event_id: (kind, e) for kind in ("mission.achieved", "mission.held", "mission.unmet",
                                                                 "mission.appraised", "cognition.settled")
                             for e in self.journal.replay(kind)}
        kind, event = self._targets.get(target, (None, None))
        if kind in ("mission.achieved", "mission.held"):
            return "closure", [self.by_receipt[r] for r in event.payload.get("evidence", []) if r in self.by_receipt]
        if kind == "mission.unmet":
            at, mid, out = self._event_seq(event), event.payload["mission_id"], []
            for check in event.payload.get("failing_checks", []):
                before = [r for r in self.readings if (r["mission_id"], r["check_id"]) == (mid, check) and r["seq"] < at]
                out += before[-1:]
            return "failure closure", out
        if kind == "cognition.settled":
            reading = self.by_event.get(event.payload.get("observation_event")) \
                or self.by_receipt.get(event.payload.get("receipt"))
            return "settled outcome", [reading] if reading else []
        if kind == "mission.appraised":
            closure = event.payload.get("closure_event") or next(
                (eid for eid, (k, e) in self._targets.items() if k == "mission.achieved"
                 and e.payload["mission_id"] == event.payload.get("mission_id")), None)
            judged = self._targets.get(closure, (None, None))[0]
            return "appraisal", self.rejected_by(closure)[1] if judged not in (None, "mission.appraised") else []
        return "other", []

    # -- causes -------------------------------------------------------------------------------------------------
    def causes(self, now: datetime, basis: dict | None = None) -> list[dict]:
        """Every cause against a reading a delivered claim rests on. ``basis`` maps a root receipt to the reading that
        last requalified it: later readings are compared with that one, and a cause on it is a new cause."""
        basis = basis or {}
        roots = {}                                          # receipt -> the delivered claims resting on it
        for claim in self.claims:
            for r in claim["receipts"]:
                roots.setdefault(r, []).append(claim["claim"])
        found = {}

        def cause(cls, root, base, why, trigger, seq, impugns, detail=None):
            cid = _cause_id(cls, root["receipt"], trigger.get("event_id") if trigger.get("kind") == "event"
                            else base["receipt"])
            if cid not in found:
                found[cid] = {"cause_id": cid, "class": cls, "why": why[:400], "impugns_measurement": impugns,
                              "root": {k: root[k] for k in ("event_id", "receipt", "mission_id", "check_id",
                                                            "capability")}
                              | {"source": (root["source"] or {}).get("key")},
                              "basis": base["receipt"], "trigger": trigger, "trigger_seq": seq,
                              **({"detail": detail} if detail else {})}
        later_by_source, later_by_sensor = defaultdict(list), defaultdict(list)
        for reading in self.readings:
            if reading["source"]:
                later_by_source[reading["source"]["key"]].append(reading)
            if reading["sensor"]:
                later_by_sensor[reading["sensor"]].append(reading)

        def at(reading):
            return {"kind": "reading", "receipt": reading["receipt"], "event_id": reading["event_id"]}
        kinds = {c["claim"]: c for c in self.claims}
        for receipt in roots:
            root = self.by_receipt[receipt]
            base = self.by_receipt.get(basis.get(receipt)) or root      # the reading the claim rests on now
            src = base["source"]
            # a standing mission's own later readings are its homeostasis: only another mission's count against a hold
            own = root["mission_id"] if all(kinds[c]["kind"] == "held" for c in roots[receipt]) else None

            def counts(later):
                return later["seq"] > base["seq"] and later["mission_id"] != own
            if src and not src["absent"]:
                for later in later_by_source[src["key"]]:
                    other = later["source"]
                    if not counts(later) or other["server_error"] or (
                            later["inconclusive"] and other["digest"] is None and not other["absent"]):
                        continue                  # a server error, or a reading that decided nothing about the bytes
                    if other["absent"]:
                        cause("SOURCE_RETRACTED", root, base, f"{src['key']} read as absent after the claim rested on it",
                              at(later), later["seq"], False)
                        break
                    if src["api"] and other["api"] and other["api"] != src["api"]:
                        cause("API_CHANGED", root, base, f"{src['key']} answers with a different final URL or status "
                              "class than when the claim rested on it", at(later), later["seq"], False,
                              {"before": src["api"], "after": other["api"]})
                        break
                    if other["digest"] != src["digest"]:
                        cause("SOURCE_CHANGED", root, base, f"{src['key']} changed from {str(src['digest'])[:16]} to "
                              f"{str(other['digest'])[:16]} after the claim rested on it", at(later), later["seq"], False)
                        break
            for text in base["expires"]:
                instant = _instant(text)
                if instant is not None and instant <= now:
                    cause("MEASUREMENT_EXPIRED", root, base, f"evidence in the reading expired at {text}",
                          {"kind": "expiry", "expires_at": text}, self.head_seq, False)
                    break
            if root["sensor"] and base["passed"]:
                computed = src is None and str(base["capability"]).startswith(COMPUTATIONS)
                for later in later_by_sensor[root["sensor"]]:
                    if not counts(later) or later["passed"] or later["inconclusive"] or later["no_method"]:
                        continue
                    if computed and later["source"] is None or (
                            src is not None and later["source"] is not None and later["source"]["key"] == src["key"]
                            and later["source"]["digest"] == src["digest"]):
                        cause("REPLICATION_FAILED", root, base, "the same signed sensor, on the same input, now fails",
                              at(later), later["seq"], True)
                        break
                    if src is None and not computed:     # a world sensor that names no digest: the world moved on
                        cause("SOURCE_CHANGED", root, base, "the same signed check now fails on a source that names "
                              "no digest", at(later), later["seq"], False)
                        break
        for e in self.journal.replay("mission.appraised"):
            p = e.payload
            if p.get("verdict") != "REFUTED":
                continue
            for claim in self.claims:
                if claim["mission_id"] == p["mission_id"] and p.get("closure_event") in (None, claim["claim"]):
                    for r in claim["receipts"]:
                        cause("APPRAISAL_REFUTED", self.by_receipt[r], self.by_receipt[r], "the closure's independent "
                              "appraisal is REFUTED", {"kind": "event", "event_id": e.event_id}, self._event_seq(e),
                              True, {"failed_checks": sorted(k for k, v in (p.get("checks") or {}).items() if v is False),
                                     "closure_event": p.get("closure_event")})
        for e in signed_rejections(self.journal):
            for reading in self.rejected_by(e.payload.get("target_event_id"))[1]:
                cause("FOUNDER_REJECTED", reading, reading, "the founder rejected it in a signed critique",
                      {"kind": "event", "event_id": e.event_id}, self._event_seq(e), True,
                      {"critique": str(e.payload.get("text", ""))[:300]})
        return sorted(found.values(), key=lambda c: (c["trigger_seq"], c["cause_id"]))

    def requalified(self, cause: dict, now: datetime) -> dict | None:
        """The later record that requalifies a cause, or None: evidence alone for every class but a founder
        rejection, which only the founder's own signed acceptance of the same answer lifts (``rejections``)."""
        if cause["class"] == "FOUNDER_REJECTED":
            by = self.rejections()[1].get((cause["trigger"].get("event_id"), cause["root"]["receipt"]))
            return None if by is None else {"event_id": by.event_id, "critique_id": by.payload.get("critique_id"),
                                            "command_digest": by.payload.get("command_digest"),
                                            "kind": "founder-signed acceptance"}
        if cause["class"] == "APPRAISAL_REFUTED":
            closure = (cause.get("detail") or {}).get("closure_event")
            for e in self.journal.replay("mission.appraised"):
                p = e.payload
                if (p.get("mission_id") == cause["root"]["mission_id"] and p.get("verdict") == "VERIFIED"
                        and p.get("closure_event") == closure and self._event_seq(e) > cause["trigger_seq"]):
                    return {"event_id": e.event_id}
            return None
        root = self.by_receipt[cause["root"]["receipt"]]
        if not root["sensor"]:
            return None
        for later in self.readings:
            if (later["sensor"] == root["sensor"] and later["passed"] and not later["inconclusive"]
                    and later["seq"] > root["seq"] and later["seq"] > cause["trigger_seq"]
                    and later["receipt"] != cause["trigger"].get("receipt")
                    and not (later["source"] and later["source"]["absent"])
                    and all((_instant(t) or now) > now for t in later["expires"])):
                return {"receipt": later["receipt"], "event_id": later["event_id"]}
        return None

    # -- descendants --------------------------------------------------------------------------------------------
    def descendants(self, cause: dict) -> dict:
        """Everything resting on the cause's root reading, each with the edge it was reached by."""
        receipts, acted_at, path = {cause["root"]["receipt"]}, {}, []      # mission -> its first affected action
        claims, actions = [], []
        if cause["class"] == "FOUNDER_REJECTED" and cause["root"]["receipt"] in self.by_receipt:
            # a rejection withholds the answer, not one receipt of it: every reading that carries it rests on it
            for other in self.same_answer(self.by_receipt[cause["root"]["receipt"]]):
                receipts.add(other["receipt"])
                path.append({"reading": other["event_id"], "by": "carries the answer the founder rejected"})
        frontier = True
        while frontier:
            frontier = False
            for claim in self.claims:
                if claim["claim"] in {c["claim"] for c in claims}:
                    continue
                cited = set(claim["receipts"]) & receipts
                acted = claim["mission_id"] in acted_at and claim["seq"] > acted_at[claim["mission_id"]]
                if cited or acted:
                    claims.append(claim)
                    path.append({"claim": claim["claim"], "by": "cites " + sorted(cited)[0][:16] if cited
                                 else "its mission acted on an affected input"})
                    frontier = True
            for e, seq in self.actions:
                if e.event_id in {a["event_id"] for a in actions}:
                    continue
                p = e.payload
                used = {b.get("from_receipt") for b in p.get("bindings") or []} | \
                       {b.get("receipt") for b in p.get("input_bindings") or []}
                hit = used & receipts
                if hit:
                    actions.append({"event_id": e.event_id, "mission_id": p["mission_id"], "action_id": p["action_id"],
                                    "receipt": p["receipt"], "scope_digest": p.get("scope_digest")})
                    path.append({"action": e.event_id, "by": "bound " + sorted(hit)[0][:16]})
                    receipts.add(p["receipt"])
                    acted_at[p["mission_id"]] = min(seq, acted_at.get(p["mission_id"], seq))
                    frontier = True
        affected_missions = {c["mission_id"] for c in claims}
        scopes = {a["scope_digest"] for a in actions if a.get("scope_digest")}
        decisions, answered = [], {e.payload.get("request_id"): e.event_id for e in
                                   self.journal.replay("decision.answered")}
        for e in self.journal.replay("decision.requested"):
            p = e.payload
            if p.get("kind") == "EVIDENCE_CORRECTION":
                continue
            text = json.dumps(p.get("evidence", ""), sort_keys=True, default=str)
            named = any(r in text for r in receipts)
            if named or p.get("scope_digest") in scopes:
                decisions.append({"request_id": p["request_id"], "kind": p.get("kind"), "mission_id": p.get("mission_id"),
                                  "answered": answered.get(p["request_id"])})
                path.append({"decision": p["request_id"], "by": "its evidence names an affected receipt" if named
                             else "it approved an action that bound an affected receipt"})
        observed = {r["event_id"] for r in self.readings if r["receipt"] in receipts}
        latest = {}
        for e in self.journal.replay("cognition.settled"):
            latest[e.payload.get("outcome_id") or e.event_id] = e
        outcomes = sorted(oid for oid, e in latest.items() if not e.payload.get("invalidated")
                          and (e.payload.get("receipt") in receipts or e.payload.get("observation_event") in observed))
        procedures = sorted(e.payload.get("procedure_id") or e.event_id for e in self.journal.replay("sop.proposed")
                            if set(e.payload.get("missions") or []) & affected_missions)
        return {"claims": [{"claim": c["claim"], "kind": c["kind"], "mission_id": c["mission_id"]} for c in claims],
                "actions": actions, "decisions": decisions, "outcomes": outcomes, "procedures": procedures,
                "receipts": sorted(receipts), "path": path,
                "unaffected_claims": len([c for c in self.claims if c["claim"] not in {x["claim"] for x in claims}])}


# -- what the body sees ----------------------------------------------------------------------------------------------

def _recorded(journal: Journal, kind: str) -> dict:
    return {e.payload["cause_id"]: e.payload for e in journal.replay(kind)}


def _basis(index: "Index", requalified: dict) -> dict:
    """root receipt -> the latest reading that requalified a cause on it: what the claim rests on now."""
    out = {}
    for q in sorted(requalified.values(), key=lambda q: index.by_receipt.get((q.get("by") or {}).get("receipt"),
                                                                           {}).get("seq", -1)):
        if (q.get("by") or {}).get("receipt") in index.by_receipt and q.get("root"):
            out[q["root"]] = q["by"]["receipt"]
    return out


def _standing_ids(index: "Index") -> dict:
    """cause id -> (critique event, rejected reading) of every founder rejection that stands (``Index.rejections``)."""
    return {_cause_id("FOUNDER_REJECTED", reading["receipt"], e.event_id): (e, reading)
            for e, reading in index.rejections()[0]}


def _lifted(correction: dict, requalified: dict, standing: dict) -> bool:
    """Whether a correction no longer holds. Evidence requalifies every class but a founder rejection (the recorded
    ``evidence.requalified``). A founder rejection is lifted only while no signed rejection of that reading stands
    (``_standing_ids``): his own signed acceptance lifted it, or no signed critique ever stood behind the record.
    A requalification record alone lifts none."""
    if correction["class"] == "FOUNDER_REJECTED":
        return correction["cause_id"] not in standing
    return correction["cause_id"] in requalified


def _standing(journal: Journal, index: "Index") -> list[tuple]:
    """(cause id, class, root receipt, what its correction recorded as affected, why) of every cause that withholds
    credit now, in order: first the recorded causes that impugn the measurement itself, are not requalified and are
    expressed by no appraisal (a REPLICATION_FAILED; a source that moved on, a changed API or an expiry is never
    among them, and a refuted appraisal is left to the readers of appraisals, ``APPRAISED``); then the founder's
    rejections that stand, read from the signed critiques themselves (``Index.rejections``), so one counts from the
    moment its command is accepted, whether or not a tick has recorded its cause, and no recorded row stands in for
    one or lifts one.

    ``why`` is what a reader is shown wherever the credit is missing: the cause and its class, its
    ``evidence.invalidated`` record (``event``: the id that record gets when the next propagation writes it, for a
    rejection accepted since the last tick), what lifts it (``lifts``), and for a founder rejection the critique
    (``rejection``) and the answer it withholds (``answer``: ``Index.identity``)."""
    requalified = _recorded(journal, "evidence.requalified")

    def why(cid, cls, **more):
        return {"cause": cls, "cause_id": cid, "event": fact_id("evidence.invalidated", [cid]), "lifts": LIFTS[cls],
                **more}
    out = [(cid, c["class"], (c.get("root") or {}).get("receipt"), c.get("affected") or {}, why(cid, c["class"]))
           for cid, c in _recorded(journal, "evidence.correction").items()
           if c.get("impugns_measurement") and cid not in requalified
           and c["class"] not in APPRAISED and c["class"] != "FOUNDER_REJECTED"]
    for cid, (e, reading) in _standing_ids(index).items():
        out.append((cid, "FOUNDER_REJECTED", reading["receipt"], {},
                    why(cid, "FOUNDER_REJECTED", rejection=e.payload.get("critique_id"),
                        answer=index.identity(reading))))
    return out


def containment(journal: Journal) -> dict:
    """What withholds credit now: {"receipts", "missions", "rejected"} (see the three readers below).

    Dependents are derived from the journal each time this is read, not taken from the ``affected`` list a
    correction stored when it was recorded: a mission that binds a contained reading after the correction was
    recorded, and a later reading that carries a rejected answer, are contained as soon as they exist, whatever
    tick recorded what. What a correction stored stays contained with it (the record is history, and it still
    names what was affected when a reading has since left the ledger). Every entry says why (``_standing``). The
    result is kept for the ledger head it was read at; do not change it."""
    try:
        head = journal.ledger.head
    except (AttributeError, IndexError):          # no ledger, or an empty one: there is no receipt to contain
        return {"receipts": {}, "missions": {}, "rejected": {}}
    kept = journal.__dict__.get("_containment")
    if kept is not None and kept[0] == head:
        return kept[1]
    out = {"receipts": {}, "missions": {}, "rejected": {}}
    if journal.replay("evidence.correction") or signed_rejections(journal):   # the usual body has neither
        index = Index(journal)
        for cid, cls, root, stored, why in _standing(journal, index):
            reached = index.descendants({"class": cls, "root": {"receipt": root}}) if root in index.by_receipt else {}
            path = reached.get("path") or stored.get("path") or []
            for r in [*reached.get("receipts", []), *(stored.get("receipts") or [])]:
                out["receipts"].setdefault(r, {**why, "path": path})
            for claim in [*reached.get("claims", []), *(stored.get("claims") or [])]:
                out["missions"].setdefault(claim["mission_id"], why)
                if cls == "FOUNDER_REJECTED":
                    out["rejected"].setdefault(claim["mission_id"], why)
    journal.__dict__["_containment"] = (head, out)
    return out


def contained_receipts(journal: Journal) -> dict:
    """receipt -> {cause, cause_id, event, path} for every receipt a standing cause reaches (``containment``): the
    reading itself, for a founder rejection every other reading that carries the rejected answer
    (``Index.same_answer``), and the receipts of the actions that bound one of them. A reader of settled outcomes
    withholds those resting on a listed receipt (``settlement.measured_outcomes``). ``path`` is the dependency
    path."""
    return containment(journal)["receipts"]


def contained_missions(journal: Journal) -> dict:
    """mission id -> {cause, cause_id, event} for every mission with a delivered claim a standing cause reaches
    (``containment``): the mission whose reading it is, a mission whose claim cites a reading that carries a
    rejected answer, and any mission whose claim followed an action that bound one. A reader of verified closures
    withholds those missions: no procedure is learned from one and it is no precedent (``sop.closed_procedures``,
    ``precedents``). The appraisal on record is not changed and nothing here touches what the mission may still
    do. A rejected failure closure contains no mission: it delivered nothing."""
    return containment(journal)["missions"]


def rejected_missions(journal: Journal) -> dict:
    """The contained missions a standing founder rejection reaches (``contained_missions`` without the failed
    replications). Routing reliability, the earned-autonomy report and precedent action evidence stop counting
    what such a mission did as a success; its failures keep counting."""
    return containment(journal)["rejected"]


def critique_effect(journal: Journal, critique: dict) -> dict | None:
    """What one founder critique does to credit, for the result of the command that carried it
    (``tribunal.critique``, which calls this before the command's acceptance is recorded).

    A rejection: what it withholds, and what lifts it. A rejection of an event that names no reading of a signed
    check (a registration, a command, an ask) is kept on the record and changes no credit; the result says so
    instead of saying nothing. An acceptance: the standing rejections it lifts, with their causes; None when it
    lifts none (most acceptances are of deliveries nobody rejected)."""
    index = Index(journal)
    what, readings = index.rejected_by(critique.get("target_event_id"))
    if critique.get("verdict") == "accept":
        accepted = {r["receipt"] for a in readings for r in (a, *index.same_answer(a))}
        lifted = sorted(cid for cid, (_, reading) in _standing_ids(index).items() if reading["receipt"] in accepted)
        if not lifted:
            return None
        return {"credit_changed": True, "accepts": what, "requalifies": lifted,
                "answers": sorted({index.identity(index.by_receipt[r]) or r for r in accepted}),
                "restores": "the credit these rejections withheld from that answer, from the acceptance of this "
                            "command on; the rejections stay on the record, and no grant, approval or capability "
                            "state is changed"}
    if not readings:
        return {"credit_changed": False, "rejects": what, "target_type": critique.get("target_type"),
                "why": "this event names no reading of a signed check, so the rejection is kept on the record and "
                       "withholds no credit and marks no claim. To withhold what an answer earned, reject its "
                       "closure, its appraisal, one of its readings or its settled outcome"}
    missions, receipts = set(), set()
    for reading in readings:
        affected = index.descendants({"class": "FOUNDER_REJECTED", "root": {"receipt": reading["receipt"]}})
        receipts.update(affected["receipts"])
        missions.update(c["mission_id"] for c in affected["claims"])
    return {"credit_changed": True, "rejects": what, "readings": sorted(r["event_id"] for r in readings),
            "answers": sorted({index.identity(r) or r["receipt"] for r in readings}),
            "receipts_withheld": len(receipts), "missions_withheld": sorted(missions),
            "withholds": "settled competence on every reading that carries a rejected answer (the same question "
                         "answered alike by the same method at the same version), and the listed missions as "
                         "evidence for a procedure, a precedent, routing reliability or an earned level; no grant, "
                         "approval or capability state is changed",
            "lifts": LIFTS["FOUNDER_REJECTED"]}


def rejection_report(journal: Journal) -> dict:
    """The founder's rejections for the morning report: which stand and what each withholds, which a signed
    acceptance has requalified, and which name no reading of a signed check and so change no credit."""
    rejections = signed_rejections(journal)
    if not rejections:
        return {"standing": [], "requalified": [], "changed_no_credit": []}
    index = Index(journal)
    standing, lifted = index.rejections()

    def named(e):
        return {"critique_id": e.payload.get("critique_id"), "target_event_id": e.payload.get("target_event_id"),
                "target_type": e.payload.get("target_type")}
    by_critique = {}
    for e, reading in standing:
        row = by_critique.setdefault(e.event_id, {**named(e), "answers": [], "missions_withheld": set(),
                                                  "lifts": LIFTS["FOUNDER_REJECTED"]})
        row["answers"].append(index.identity(reading) or reading["receipt"])
        row["missions_withheld"].update(c["mission_id"] for c in index.descendants(
            {"class": "FOUNDER_REJECTED", "root": {"receipt": reading["receipt"]}})["claims"])
    by_event = {e.event_id: e for e in rejections}
    requalified = {}
    for (rejection, _), by in lifted.items():
        requalified[rejection, by.event_id] = {**named(by_event[rejection]),
                                               "requalified_by": by.payload.get("critique_id"),
                                               "command_digest": by.payload.get("command_digest")}
    return {"standing": [{**row, "answers": sorted(row["answers"]), "missions_withheld": sorted(row["missions_withheld"])}
                         for row in by_critique.values()],
            "requalified": list(requalified.values()),
            "changed_no_credit": [named(e) for e in rejections
                                  if not index.rejected_by(e.payload.get("target_event_id"))[1]]}


def claims(journal: Journal, now: datetime) -> list[dict]:
    """Every delivered claim with its freshness and its correction state: CURRENT, EXPIRED or NEEDS_REVIEW.

    A claim is NEEDS_REVIEW while a cause that is not lifted reaches it: one a correction recorded for it, or one
    reached now (a claim that cites a reading carrying a rejected answer, or that followed an action which bound an
    affected receipt after the correction was recorded). A founder rejection counts from its signed critique, and
    stops counting from the founder's signed acceptance of the same answer."""
    index = Index(journal)
    corrections, requalified = _recorded(journal, "evidence.correction"), _recorded(journal, "evidence.requalified")
    standing = _standing_ids(index)
    signed = {cid: reading["receipt"] for cid, (_, reading) in standing.items()}
    open_causes = []                      # (cause id, class, root receipt, the claims its correction recorded)
    for cid, correction in corrections.items():
        if _lifted(correction, requalified, standing):
            continue
        open_causes.append((cid, correction["class"], (correction.get("root") or {}).get("receipt"),
                            [c["claim"] for c in correction["affected"]["claims"]]))
    open_causes += [(cid, "FOUNDER_REJECTED", root, []) for cid, root in signed.items() if cid not in corrections]
    marked = defaultdict(list)
    for cid, cls, root, stored in open_causes:
        reached = [c["claim"] for c in index.descendants({"class": cls, "root": {"receipt": root}})["claims"]] \
            if root in index.by_receipt else []
        for claim in dict.fromkeys(stored + reached):
            marked[claim].append(cid)
    out, basis = [], _basis(index, requalified)
    for claim in index.claims:
        readings = [index.by_receipt[basis.get(r, r)] for r in claim["receipts"]]
        confirmed = []
        for r in readings:
            same = [x for x in index.readings if r["source"] and x["source"] and x["source"]["key"] == r["source"]["key"]
                    and x["source"]["digest"] == r["source"]["digest"]]
            confirmed.append(max((x["at"] or "" for x in same), default=r["at"]))
        until = min((t for r in readings for t in r["expires"] if _instant(t)), default=None, key=_instant)
        expired = until is not None and _instant(until) <= now
        state = "NEEDS_REVIEW" if marked[claim["claim"]] else "EXPIRED" if expired else "CURRENT"
        out.append({**{k: claim[k] for k in ("claim", "kind", "mission_id", "at")}, "state": state,
                    "sources": sorted({r["source"]["key"] for r in readings if r["source"]}),
                    "confirmed_at": min(confirmed, default=None), "fresh_until": until,
                    "corrections": marked[claim["claim"]]})
    return out


def _quoted(index: Index, group: list[dict]) -> list[str]:
    """The founder's own words an ask quotes (signed mission specs, source locators, a critique): never screened as
    GREG's."""
    missions = {c["root"]["mission_id"] for c in group} | {x["mission_id"] for c in group for x in c["affected"]["claims"]}
    words = asks.founder_text([index.specs.get(m) for m in sorted(missions)])
    return words + asks.founder_text([[c["root"].get("source"), (c.get("detail") or {}).get("critique")] for c in group])


def _group_id(cause: dict) -> str:
    """One ask per triggering record and mission: a change, rejection or refutation that touches several readings of
    one mission is one question, not one per reading."""
    trigger = {k: v for k, v in cause["trigger"].items() if k in ("kind", "receipt", "event_id", "expires_at")}
    return "correction-" + sha256_json({"trigger": trigger, "mission": cause["root"]["mission_id"]})[7:31]


def _union(group: list[dict], field: str, key: str) -> list:
    seen, out = set(), []
    for c in group:
        for x in c["affected"][field]:
            if x[key] not in seen:
                seen.add(x[key])
                out.append(x)
    return out


def _ask(group: list[dict]) -> dict:
    """The ask for one group of corrections, built only from what they recorded (so it is the same on every tick)."""
    first = group[0]
    claims, decisions = _union(group, "claims", "claim"), _union(group, "decisions", "request_id")
    procedures = sorted({p for c in group for p in c["affected"]["procedures"]})
    total = first["affected"]["unaffected_claims"] + len(first["affected"]["claims"])
    return {"request_id": first["request_id"], "kind": "EVIDENCE_CORRECTION",
            "mission_id": first["root"]["mission_id"], "action_id": None, "scope_digest": first["cause_id"],
            "why_now": f"{first['class']}: {first['why']}" + (f" (and {len(group) - 1} more reading(s) of this mission)"
                                                              if len(group) > 1 else ""),
            "recommendation": f"review {len(claims)} delivered claim(s) and {len(decisions)} decision(s) that rest on "
                              "it; re-run the affected missions if their answers still matter",
            "alternatives": ["keep the claims as delivered, marked NEEDS_REVIEW (costs nothing)",
                             "sign a new mission that re-reads the source and answers again"],
            "evidence": {"causes": [{k: c[k] for k in ("cause_id", "class", "root")}
                                    | ({"detail": c["detail"]} if c.get("detail") else {}) for c in group],
                         "affected": {"claims": claims, "decisions": decisions, "procedures": procedures},
                         "unaffected_claims": total - len(claims)},
            "authority_requested": {"command": None, "spend": "none"},
            "consequence_of_no_response": "nothing is undone: the claims stay delivered and marked NEEDS_REVIEW, and "
                                          "every decision listed stays as the founder made it",
            "created_at": first["at"], "reality_status": "RECORDED_LOCAL_MESSAGE"}


def propagate(journal: Journal, now: datetime) -> list[dict]:
    """Record every new cause with the correction it propagates; ask when the founder has something to review;
    record a requalification found by evidence. Writes no grant, approval or capability state."""
    if not journal.replay("mission.achieved") and not journal.replay("mission.held") \
            and not signed_rejections(journal):
        return []                     # nothing delivered and nothing rejected: no index to build on this tick
    index, recorded = Index(journal), []
    corrected, requalified = _recorded(journal, "evidence.correction"), _recorded(journal, "evidence.requalified")
    invalidated = _recorded(journal, "evidence.invalidated")
    answered = {e.payload.get("request_id") for e in journal.replay("decision.answered")}
    causes, standing = index.causes(now, _basis(index, requalified)), _standing_ids(index)
    for cause in causes:                 # 1. each new cause and its correction, written once, before any ask
        cid = cause["cause_id"]
        if cid in corrected:
            continue
        if journal.retained("evidence.invalidated", [cid]) is None:
            journal.record("evidence.invalidated", {**cause, "at": iso(now)}, key=[cid])
            invalidated[cid] = cause
        affected = index.descendants(cause)
        correction = {"cause_id": cid, "class": cause["class"], "why": cause["why"],
                      "impugns_measurement": cause["impugns_measurement"], "root": cause["root"],
                      **({"detail": cause["detail"]} if cause.get("detail") else {}),
                      "affected": affected, "applied": False, "authority_created": False,
                      "history_rewritten": False, "at": iso(now)}
        terminal = cause["class"] not in SELF_REPORTED and any(c["kind"] == "achieved" for c in affected["claims"])
        outside = any(a["mission_id"] != cause["root"]["mission_id"] for a in affected["actions"])
        if terminal or outside or affected["decisions"]:
            correction["request_id"] = _group_id(cause)
        journal.record("evidence.correction", correction, key=[cid, "correction"])
        recorded.append(correction)
        corrected[cid] = correction
    for cause in causes:                 # 2. requalification by evidence alone, against the trigger as recorded
        cid = cause["cause_id"]
        if cid in requalified:
            continue
        by = index.requalified(invalidated.get(cid, cause), now)
        if by is not None:
            journal.record("evidence.requalified", {"cause_id": cid, "root": cause["root"]["receipt"], "by": by,
                                                    "restores_permission": False, "at": iso(now)},
                           key=[cid, "requalified"])
            requalified[cid] = {"by": by}
    groups = defaultdict(list)
    for c in sorted(corrected.values(), key=lambda c: c["cause_id"]):
        if c.get("request_id"):
            groups[c["request_id"]].append(c)
    for rid, group in groups.items():    # 3. one ask per group, from the stored records; withdrawn once all requalify
        open_causes = [c for c in group if not _lifted(c, requalified, standing)]
        asked = journal.retained("decision.requested", rid) is not None
        if open_causes and not asked:
            asks.record(journal, _ask(group), quoted=_quoted(index, group))
        elif not open_causes and asked and rid not in answered \
                and journal.retained("decision.withdrawn", [rid, "withdrawn"]) is None:
            journal.record("decision.withdrawn", {"request_id": rid, "mission_id": group[0]["root"]["mission_id"],
                                                  "why": "requalified: a later record of the same signed check "
                                                         "holds again, or the founder accepted what he had rejected",
                                                  "at": iso(now)}, key=[rid, "withdrawn"])
    return recorded


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
