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

A **cause** is found when a later record contradicts a reading a delivered claim rests on:

- SOURCE_CHANGED: the same source read later with a different digest; SOURCE_RETRACTED: read later as absent (a
  missing file, HTTP 404 or 410);
- API_CHANGED: the same URL answering with a different final URL or status class (a server error, 5xx, is not a
  reading of the source at all). A capability later quarantined because its identity changed is not a cause: every
  adapter re-checks its pinned identity before each run, so what it read before was read by what was verified;
- MEASUREMENT_EXPIRED: an ``expires_at`` of an evidence source in one of GREG's own cognition receipts has passed
  (an expiry inside other data, an MCP server's for instance, is that data's, not the measurement's);
- REPLICATION_FAILED: the same signed sensor (instrument, input and predicate) read later fails on the same input
  (the same source digest, or a computation with no source); APPRAISAL_REFUTED: the closure's independent appraisal is
  REFUTED; FOUNDER_REJECTED: a founder critique rejects the closure or the reading.

Each cause is recorded once (``evidence.invalidated``), with the correction it propagates (``evidence.correction``:
every affected descendant and the edge it was reached by, and how many delivered claims are unaffected). History is
never edited. Only the causes that impugn the measurement itself (replication on the same input, a refuted appraisal,
a founder rejection) contain the settled outcomes on it (``contained_receipts``): a source that moved on leaves the
method that read it as competent as before. Every cause marks its claims NEEDS_REVIEW and names the decisions to
review; a terminal delivery, or one another mission or a founder decision depended on, is also put to the founder,
once per triggering record and mission (EVIDENCE_CORRECTION, answer only recorded), from the stored correction.

A cause is **requalified** by evidence alone (``evidence.requalified``): a later passing reading of the same signed
sensor, with no expired evidence of its own; a refuted appraisal only by a later
VERIFIED appraisal of the same closure; a founder rejection never by evidence. The requalifying reading becomes the
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
from greg.journal import Journal, iso
from provenance.ledger import sha256_json

CLASSES = ("SOURCE_CHANGED", "SOURCE_RETRACTED", "API_CHANGED", "MEASUREMENT_EXPIRED", "REPLICATION_FAILED",
           "APPRAISAL_REFUTED", "FOUNDER_REJECTED")
RETRACTED_STATUS = (404, 410)
# Causes whose trigger is itself a record the founder already sees and the machine already acts on: a refuted
# appraisal of the mission's own closure (autonomy, routing and Goal Gravity consume it) and the founder's own
# rejection. They put an ask only when something beyond that mission rests on the claim.
SELF_REPORTED = ("APPRAISAL_REFUTED", "FOUNDER_REJECTED")
COMPUTATIONS = ("cognition.",)        # sensors whose reading is a computation on its signed input, not the world
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
                s = check.get("sensor") or {}
                sensors[(e.payload["mission_id"], check["check_id"])] = sha256_json(   # instrument, input and claim
                    {"sensor": s.get("capability") or s.get("function"), "params": s.get("params", {}),
                     "predicate": check.get("predicate")})
        self.readings, self.by_receipt = [], {}
        for e in journal.replay("mission.observed"):
            p = e.payload
            record = ledger.find(p["receipt"]) if p.get("receipt") else None
            if record is None:
                continue
            output = (record.payload.get("result") or {}).get("output")
            own = str(p.get("capability", "")).startswith("cognition.")     # GREG's own receipts carry evidence
            reading = {"event_id": e.event_id, "mission_id": p["mission_id"], "check_id": p["check_id"],
                       "receipt": p["receipt"], "seq": record.seq, "capability": p.get("capability"),
                       "passed": bool(p.get("passed")), "inconclusive": str(p.get("detail", "")).startswith("sensor "),
                       "sensor": sensors.get((p["mission_id"], p["check_id"])), "source": source_of(output),
                       "expires": sorted(expiries(output)) if own else [], "at": p.get("at")}
            self.readings.append(reading)
            self.by_receipt[p["receipt"]] = reading
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
            cid = "cause-" + sha256_json({"class": cls, "root": root["receipt"],
                                          "on": trigger.get("event_id") if trigger.get("kind") == "event"
                                          else base["receipt"]})[7:39]
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
                    if not counts(later) or later["passed"] or later["inconclusive"]:
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
        claim_of = {c["claim"]: c for c in self.claims}
        for e in self.journal.replay("mission.appraised"):
            p = e.payload
            if p.get("verdict") != "REFUTED":
                continue
            for claim in self.claims:
                if claim["mission_id"] == p["mission_id"] and p.get("closure_event") in (None, claim["claim"]):
                    for r in claim["receipts"]:
                        cause("APPRAISAL_REFUTED", self.by_receipt[r], self.by_receipt[r], "the closure's independent "
                              "appraisal is REFUTED", {"kind": "event", "event_id": e.event_id}, self._event_seq(e),
                              True, {"failed_checks": sorted(k for k, v in (p.get("checks") or {}).items() if v is False
                                                             and k not in (p.get("not_established") or ())),
                                     "closure_event": p.get("closure_event")})
        for e in self.journal.replay("critique.recorded"):
            p = e.payload
            if p.get("verdict") != "reject":
                continue
            target = p.get("target_event_id")
            hits = claim_of[target]["receipts"] if target in claim_of else \
                [r["receipt"] for r in self.readings if r["event_id"] == target and r["receipt"] in roots]
            for r in hits:
                cause("FOUNDER_REJECTED", self.by_receipt[r], self.by_receipt[r], "the founder rejected it in a signed "
                      "critique", {"kind": "event", "event_id": e.event_id}, self._event_seq(e), True,
                      {"critique": str(p.get("text", ""))[:300]})
        return sorted(found.values(), key=lambda c: (c["trigger_seq"], c["cause_id"]))

    def requalified(self, cause: dict, now: datetime) -> dict | None:
        """The later record that requalifies a cause by evidence alone, or None."""
        if cause["class"] == "FOUNDER_REJECTED":
            return None
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


def contained_receipts(journal: Journal) -> dict:
    """receipt -> {cause, cause_id, event, path} for every recorded cause that impugns the measurement itself
    (REPLICATION_FAILED, APPRAISAL_REFUTED, FOUNDER_REJECTED) and is not requalified. A reader of settled outcomes
    withholds those resting on a listed receipt; a source that moved on, a changed API or an expiry lists nothing.
    ``event`` is the ``evidence.invalidated`` event id; ``path`` the dependency path of the correction. Computed from
    recorded facts only (deterministic, cheap)."""
    requalified = _recorded(journal, "evidence.requalified")
    events = {e.payload["cause_id"]: e.event_id for e in journal.replay("evidence.invalidated")}
    out = {}
    for cid, correction in _recorded(journal, "evidence.correction").items():
        if correction.get("impugns_measurement") and cid not in requalified:
            for r in correction["affected"]["receipts"]:
                out.setdefault(r, {"cause": correction["class"], "cause_id": cid, "event": events.get(cid),
                                   "path": correction["affected"]["path"]})
    return out


def claims(journal: Journal, now: datetime) -> list[dict]:
    """Every delivered claim with its freshness and its correction state: CURRENT, EXPIRED or NEEDS_REVIEW."""
    index = Index(journal)
    corrections, requalified = _recorded(journal, "evidence.correction"), _recorded(journal, "evidence.requalified")
    marked = defaultdict(list)
    for cid, correction in corrections.items():
        if cid not in requalified:
            for c in correction["affected"]["claims"]:
                marked[c["claim"]].append(cid)
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
    if not journal.replay("mission.achieved") and not journal.replay("mission.held"):
        return []                                    # nothing delivered: no index to build on this tick
    index, recorded = Index(journal), []
    corrected, requalified = _recorded(journal, "evidence.correction"), _recorded(journal, "evidence.requalified")
    invalidated = _recorded(journal, "evidence.invalidated")
    answered = {e.payload.get("request_id") for e in journal.replay("decision.answered")}
    causes = index.causes(now, _basis(index, requalified))
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
        open_causes = [c for c in group if c["cause_id"] not in requalified]
        asked = journal.retained("decision.requested", rid) is not None
        if open_causes and not asked:
            asks.record(journal, _ask(group), quoted=_quoted(index, group))
        elif not open_causes and asked and rid not in answered \
                and journal.retained("decision.withdrawn", [rid, "withdrawn"]) is None:
            journal.record("decision.withdrawn", {"request_id": rid, "mission_id": group[0]["root"]["mission_id"],
                                                  "why": "requalified: a later record of the same signed check "
                                                         "holds again", "at": iso(now)}, key=[rid, "withdrawn"])
    return recorded


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
