"""#45 Security monitoring: detection rules over GREG's journal; every confirmed incident becomes a rule.

Rules are data, stored as a versioned object (#3) so every change has a reason,
evidence and a rollback. Four rule shapes cover the five categories:

  burst   N matching events inside a window (identity: rejected founder commands)
  match   one matching event is enough (derived rules are this shape)
  spike   an event's numeric field above k x the running median for its group (spend)
  streak  N consecutive matching events for a group (outcomes: REFUTED appraisals)

Events are GREG journal entries (``command.rejected``, ``mission.action``,
``mission.appraised``...). ``detect`` returns alerts citing event ids.
``confirm`` records the incident and derives a narrower ``match`` rule from what
the incident's events share (e.g. the exact refusal reason or the target), so
the same attack is caught on its first occurrence next time. ``dismiss``
records a false positive; nothing is deleted. Detection only reports: it never
blocks or acts — containment stays with GREG's pause/stop and the founder.
"""
from __future__ import annotations

import re
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from foundry.systems import versions

BASE_RULES = [
    {"id": "identity.burst", "category": "identity", "type": "burst", "event": "command.rejected",
     "where": {"reason": "FounderAuthError"}, "threshold": 3, "window_s": 600, "group_by": None},
    {"id": "network.outside_scope", "category": "network", "type": "match", "event": "mission.action",
     "where": {"status": "^(REFUSED|OUTSIDE_SCOPE)$", "reasons": "target"}, "threshold": 1, "group_by": "mission_id"},
    {"id": "credential.secret_refused", "category": "credential", "type": "match", "event": "mission.action",
     "where": {"reasons": "(?i)secret|credential"}, "threshold": 1, "group_by": "capability"},
    {"id": "spend.spike", "category": "spend", "type": "spike", "event": "mission.action", "field": "cost_usd",
     "factor": 5.0, "min_history": 3, "where": {"status": "^DONE$"}, "group_by": "capability"},
    {"id": "outcome.refuted_streak", "category": "outcome", "type": "streak", "event": "mission.appraised",
     "where": {"verdict": "^REFUTED$"}, "threshold": 2, "group_by": "capability"},
]


class SiemError(ValueError):
    pass


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _kind(e: dict) -> str:
    return e["type"].removeprefix("greg.")


def _field(e: dict, name: str) -> str:
    v = e["payload"].get(name)
    return " | ".join(map(str, v)) if isinstance(v, list) else ("" if v is None else str(v))


def _matches(e: dict, rule: dict) -> bool:
    return _kind(e) == rule["event"] and all(re.search(p, _field(e, f)) for f, p in rule.get("where", {}).items())


def rules(root: Path) -> list[dict]:
    if versions.head(Path(root) / "rules", "siem-rules") is None:
        return [dict(r) for r in BASE_RULES]
    return versions.content(Path(root) / "rules", "siem-rules")


def detect(events: list[dict], ruleset: list[dict]) -> list[dict]:
    events = sorted(events, key=lambda e: (e["at"], e["event_id"]))
    alerts = []
    for rule in ruleset:
        group = lambda e: _field(e, rule["group_by"]) if rule.get("group_by") else "*"
        if rule["type"] == "match":
            for e in events:
                if _matches(e, rule):
                    alerts.append({"rule": rule["id"], "category": rule["category"], "group": group(e),
                                   "events": [e["event_id"]], "at": e["at"]})
        elif rule["type"] == "burst":
            hits = [e for e in events if _matches(e, rule)]
            start = 0
            for i, e in enumerate(hits):
                while (_t(e["at"]) - _t(hits[start]["at"])).total_seconds() > rule["window_s"]:
                    start += 1
                if i - start + 1 == rule["threshold"]:
                    alerts.append({"rule": rule["id"], "category": rule["category"], "group": "*",
                                   "events": [h["event_id"] for h in hits[start:i + 1]], "at": e["at"]})
        elif rule["type"] == "spike":
            history: dict[str, list[float]] = defaultdict(list)
            for e in events:
                if not _matches(e, rule):
                    continue
                g, value = group(e), float(e["payload"].get(rule["field"]) or 0.0)
                past = history[g]
                if len(past) >= rule["min_history"] and value > rule["factor"] * max(statistics.median(past), 1e-9):
                    alerts.append({"rule": rule["id"], "category": rule["category"], "group": g,
                                   "events": [e["event_id"]], "at": e["at"], "value": value,
                                   "baseline_median": statistics.median(past)})
                past.append(value)
        elif rule["type"] == "streak":
            run: dict[str, list[str]] = defaultdict(list)
            for e in events:
                if _kind(e) != rule["event"]:
                    continue
                g = group(e)
                if _matches(e, rule):
                    run[g].append(e["event_id"])
                    if len(run[g]) == rule["threshold"]:
                        alerts.append({"rule": rule["id"], "category": rule["category"], "group": g,
                                       "events": list(run[g]), "at": e["at"]})
                else:
                    run[g] = []
        else:
            raise SiemError(f"unknown rule type {rule['type']!r}")
    return sorted(alerts, key=lambda a: (a["at"], a["rule"]))


def _derive(alert: dict, events: list[dict], ruleset: list[dict]) -> dict:
    """A narrower rule from what the incident's events share: fires on the first recurrence."""
    base = next(r for r in ruleset if r["id"] == alert["rule"])
    hit = [e for e in events if e["event_id"] in alert["events"]]
    where = {}
    for name in ("reason", "reasons", "target", "capability", "verdict"):
        values = {_field(e, name) for e in hit}
        if len(values) == 1 and values != {""}:
            value = values.pop()
            if name in ("reason", "reasons"):  # keep the stable prefix, not ids or timestamps
                value = re.split(r"[0-9a-f]{8,}|\d{4}-\d\d-\d\d", value)[0][:80]
            where[name] = "^" + re.escape(value) if value else ".*"
    if not where:
        raise SiemError("incident events share no field to derive a rule from")
    rid = f"derived.{base['category']}.{len([r for r in ruleset if r['id'].startswith('derived.')]) + 1}"
    return {"id": rid, "category": base["category"], "type": "match", "event": base["event"], "where": where,
            "threshold": 1, "group_by": base.get("group_by"), "derived_from": alert["rule"],
            "incident_events": alert["events"]}


def confirm(root: Path, alert: dict, events: list[dict], *, note: str) -> dict:
    ruleset = rules(root)
    new_rule = _derive(alert, events, ruleset)
    if any(r.get("where") == new_rule["where"] and r["event"] == new_rule["event"] for r in ruleset):
        return {"incident": alert["events"], "rule": None, "why": "an identical rule already exists"}
    versions.commit(Path(root) / "incidents", "incidents", {"alert": alert, "note": note, "state": "confirmed"},
                    reason=note, evidence=alert["events"])
    record = versions.commit(Path(root) / "rules", "siem-rules", ruleset + [new_rule],
                             reason=f"incident {alert['rule']}: {note}", evidence=alert["events"])
    return {"incident": alert["events"], "rule": new_rule["id"], "ruleset_version": record["n"]}


def dismiss(root: Path, alert: dict, *, note: str) -> dict:
    record = versions.commit(Path(root) / "incidents", "incidents", {"alert": alert, "note": note,
                                                                     "state": "false_positive"},
                             reason=note, evidence=alert["events"])
    return {"dismissed": alert["events"], "version": record["n"]}


QUERY_OPS = {"detect": lambda a, r: {"alerts": detect(a["events"], rules(r))},
             "rules": lambda a, r: {"rules": rules(r)}}
APPLY_OPS = {"confirm": lambda a, r: confirm(r, a["alert"], a["events"], note=a["note"]),
             "dismiss": lambda a, r: dismiss(r, a["alert"], note=a["note"])}


def _ev(n, kind, at, **payload):
    return {"type": "greg." + kind, "event_id": f"e{n:03d}", "at": at, "payload": payload}


def sample_week(week: int) -> list[dict]:
    d = f"2026-09-{week * 7:02d}"
    forged = "FounderAuthError: signature does not verify"
    ev = [_ev(week * 100 + i, "mission.action", f"{d}T0{i}:00:00Z", mission_id="m:quotes", capability="wmi.assess",
              status="DONE", cost_usd=0.02, reasons=[]) for i in range(1, 5)]
    if week == 1:
        ev += [_ev(150 + i, "command.rejected", f"{d}T10:0{i}:00Z", file=f"x{i}.json", reason=forged)
               for i in range(3)]
        ev += [_ev(160, "mission.action", f"{d}T11:00:00Z", mission_id="m:quotes", capability="wmi.assess",
                   status="DONE", cost_usd=0.5, reasons=[])]
        ev += [_ev(170 + i, "mission.appraised", f"{d}T12:0{i}:00Z", mission_id="m:quotes", capability="wmi.assess",
                   verdict="REFUTED") for i in range(2)]
        ev += [_ev(180, "mission.action", f"{d}T13:00:00Z", mission_id="m:quotes", capability="web.fetch",
                   status="REFUSED", reasons=["target evil.example is outside the mission cone"], cost_usd=0.0)]
        ev += [_ev(190, "mission.action", f"{d}T14:00:00Z", mission_id="m:quotes", capability="web.fetch",
                   status="REFUSED", reasons=["secret broker: stripe_key is not granted to web.fetch"], cost_usd=0.0)]
    else:
        ev += [_ev(250, "command.rejected", f"{d}T10:00:00Z", file="y.json", reason=forged)]
    return ev


def exercise(root) -> dict:
    root = Path(root)
    week1, week2 = sample_week(1), sample_week(2)
    alerts1 = detect(week1, rules(root))
    by_rule = {a["rule"]: a for a in alerts1}
    before = [a["rule"] for a in detect(week2, rules(root))]
    confirmed = confirm(root, by_rule["identity.burst"], week1, note="forged founder commands: key not ours")
    again = confirm(root, by_rule["identity.burst"], week1, note="same incident twice")
    dismissed = dismiss(root, by_rule["spend.spike"], note="founder bought a larger dataset on purpose")
    after = detect(week2, rules(root))
    history = versions.history(root / "rules", "siem-rules")
    return {"week1_alerts": sorted({(a["category"], a["rule"]) for a in alerts1}),
            "week2_single_forgery_before_learning": before,
            "derived_rule": confirmed["rule"], "duplicate_rule_refused": again["rule"] is None,
            "week2_single_forgery_after_learning": [(a["rule"], a["events"]) for a in after],
            "rule_versions": [(h["n"], h["reason"]) for h in history], "false_positive_recorded": dismissed["version"]}
