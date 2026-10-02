"""#44 Observability: GREG's journal correlated by mission, with "why did this metric change".

Every GREG event carries a mission id. ``correlate`` turns the journal into one
trace per mission: registration, founder decisions (requested -> answered, with
latency), actions (capability, status, receipt, cost), observations, blocks and
appraised outcomes, in time order. ``metrics`` computes institutional numbers
over a window (closures, verified-appraisal rate, actions, blocks, decision
latency, cost). ``why_changed`` compares two windows and attributes the delta
to the missions and capabilities whose events moved it, citing event ids.
``otel_spans`` exports the same traces in the OpenTelemetry span shape
(trace id per mission, span per event) so a standard collector can ingest them;
no collector is bundled or contacted.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime

METRICS = ("closures", "verified_rate", "actions", "blocks", "decision_latency_s", "cost_usd")


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _kind(e: dict) -> str:
    return e["type"].removeprefix("greg.")


def correlate(events: list[dict], mission_id: str | None = None) -> dict:
    traces: dict[str, list] = defaultdict(list)
    requested: dict[str, str] = {}
    last_capability: dict[str, str] = {}
    for e in sorted(events, key=lambda e: (e["at"], e["event_id"])):
        p, kind = e["payload"], _kind(e)
        mid = p.get("mission_id")
        if not mid or (mission_id and mid != mission_id):
            continue
        span = {"event_id": e["event_id"], "at": e["at"], "kind": kind}
        if kind == "decision.requested":
            requested[p["request_id"]] = e["at"]
            span.update(request_id=p["request_id"], capability=(p.get("authority_requested") or {}).get("capability"))
        elif kind == "decision.answered":
            asked = requested.get(p["request_id"])
            span.update(request_id=p["request_id"], answer=p.get("answer"),
                        latency_s=(_t(e["at"]) - _t(asked)).total_seconds() if asked else None)
        elif kind == "mission.action":
            last_capability[mid] = p.get("capability")
            span.update(capability=p.get("capability"), status=p.get("status"), receipt=p.get("receipt"),
                        cost_usd=float(p.get("cost_usd") or 0.0))
        elif kind == "mission.appraised":
            span.update(verdict=p.get("verdict"))
        elif kind in ("mission.blocked", "mission.lifecycle"):
            span.update(reason=p.get("reason") or p.get("state"))
        if kind in ("mission.achieved", "mission.appraised", "mission.blocked") and "capability" not in span:
            span["capability"] = p.get("capability") or last_capability.get(mid)
        traces[mid].append(span)
    return {"missions": {m: {"spans": s, "trace_id": hashlib.sha256(m.encode()).hexdigest()[:32]}
                         for m, s in sorted(traces.items())}}


def _in(e: dict, start: str | None, end: str | None) -> bool:
    return (start is None or e["at"] >= start) and (end is None or e["at"] < end)


def _contributions(events: list[dict], start: str | None, end: str | None) -> dict:
    """Per metric: {(mission, capability): (numerator, denominator, [event ids])}."""
    rows = {m: defaultdict(lambda: [0.0, 0.0, []]) for m in METRICS}
    trace = correlate([e for e in events if _in(e, start, end)])
    for mid, t in trace["missions"].items():
        for s in t["spans"]:
            key = (mid, s.get("capability") or "-")
            if s["kind"] == "mission.achieved":
                r = rows["closures"][key]; r[0] += 1; r[1] = 1; r[2].append(s["event_id"])
            elif s["kind"] == "mission.appraised":
                r = rows["verified_rate"][key]; r[0] += s.get("verdict") == "VERIFIED"; r[1] += 1; r[2].append(s["event_id"])
            elif s["kind"] == "mission.action":
                r = rows["actions"][key]; r[0] += 1; r[1] = 1; r[2].append(s["event_id"])
                c = rows["cost_usd"][key]; c[0] += s["cost_usd"]; c[1] = 1; c[2].append(s["event_id"])
            elif s["kind"] == "mission.blocked":
                r = rows["blocks"][key]; r[0] += 1; r[1] = 1; r[2].append(s["event_id"])
            elif s["kind"] == "decision.answered" and s.get("latency_s") is not None:
                r = rows["decision_latency_s"][key]; r[0] += s["latency_s"]; r[1] += 1; r[2].append(s["event_id"])
    return rows


def _value(metric: str, rows: dict) -> float | None:
    num = sum(r[0] for r in rows.values())
    if metric in ("verified_rate", "decision_latency_s"):
        den = sum(r[1] for r in rows.values())
        return round(num / den, 4) if den else None
    return round(num, 4)


def metrics(events: list[dict], *, start: str | None = None, end: str | None = None) -> dict:
    rows = _contributions(events, start, end)
    return {m: _value(m, rows[m]) for m in METRICS}


def why_changed(events: list[dict], metric: str, *, split: str, start: str | None = None,
                end: str | None = None) -> dict:
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; metrics are {METRICS}")
    before, after = _contributions(events, start, split)[metric], _contributions(events, split, end)[metric]
    v0, v1 = _value(metric, before), _value(metric, after)
    drivers = []
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key, [0, 0, []]), after.get(key, [0, 0, []])
        delta = a[0] - b[0] if metric not in ("verified_rate", "decision_latency_s") else \
            (a[0] / a[1] if a[1] else 0) * a[1] - (b[0] / b[1] if b[1] else 0) * b[1]
        if a[:2] != b[:2]:
            drivers.append({"mission_id": key[0], "capability": key[1], "before": b[:2], "after": a[:2],
                            "delta": round(delta, 4), "events": a[2] or b[2]})
    anomalies = [s for mid, t in correlate([e for e in events if _in(e, split, end)])["missions"].items()
                 for s in t["spans"] if s["kind"] == "mission.blocked" or s.get("verdict") not in (None, "VERIFIED")
                 or (s.get("answer") not in (None, "approve"))]
    for d in drivers:
        d["after_window_anomalies"] = [{k: a[k] for k in ("event_id", "kind", "reason", "verdict") if k in a}
                                       for a in anomalies if a["event_id"] in
                                       {s["event_id"] for s in correlate(events, d["mission_id"])["missions"]
                                        .get(d["mission_id"], {"spans": []})["spans"]}]
    drivers.sort(key=lambda d: (-abs(d["delta"]), d["mission_id"]))
    direction = None if v0 is None or v1 is None else ("up" if v1 > v0 else "down" if v1 < v0 else "flat")
    return {"metric": metric, "before": v0, "after": v1, "direction": direction, "drivers": drivers}


def otel_spans(events: list[dict]) -> list[dict]:
    out = []
    for mid, t in correlate(events)["missions"].items():
        root = None
        for s in t["spans"]:
            span_id = hashlib.sha256(s["event_id"].encode()).hexdigest()[:16]
            ns = int(_t(s["at"]).timestamp() * 1e9)
            out.append({"traceId": t["trace_id"], "spanId": span_id, "parentSpanId": root or "", "name": s["kind"],
                        "startTimeUnixNano": ns, "endTimeUnixNano": ns,
                        "attributes": [{"key": f"greg.{k}", "value": {"stringValue": str(v)}}
                                       for k, v in sorted(s.items()) if k not in ("event_id", "at", "kind") and v is not None]
                        + [{"key": "greg.mission_id", "value": {"stringValue": mid}}]})
            root = root or span_id
    return out


QUERY_OPS = {"correlate": lambda a, r: correlate(a["events"], a.get("mission_id")),
             "metrics": lambda a, r: metrics(a["events"], start=a.get("start"), end=a.get("end")),
             "why_changed": lambda a, r: why_changed(a["events"], a["metric"], split=a["split"],
                                                     start=a.get("start"), end=a.get("end")),
             "otel": lambda a, r: {"spans": otel_spans(a["events"])}}
APPLY_OPS: dict = {}


def sample_events() -> list[dict]:
    """A GREG-shaped journal: two weeks, a capability that starts failing in week two."""
    ev, n = [], 0
    def add(kind, at, **payload):
        nonlocal n
        n += 1
        ev.append({"type": "greg." + kind, "event_id": f"ev-{n:03d}", "at": at, "payload": payload})
    for week, day in ((1, "2026-09-0"), (2, "2026-09-1")):
        for i, mid in enumerate(("m:quotes", "m:research")):
            d = f"{day}{i + 1}T09:00:00Z"
            add("mission.registered", d, mission_id=mid, spec={"founder_expression": mid})
            add("decision.requested", f"{day}{i + 1}T09:05:00Z", mission_id=mid, request_id=f"r{week}{i}",
                authority_requested={"capability": "foundry.apply"})
            add("decision.answered", f"{day}{i + 1}T{'09:35' if week == 2 and mid == 'm:quotes' else '09:10'}:00Z",
                mission_id=mid, request_id=f"r{week}{i}", answer="approve")
            cap = "wmi.assess" if mid == "m:quotes" else "web.fetch"
            add("mission.action", f"{day}{i + 1}T10:00:00Z", mission_id=mid, capability=cap, status="DONE",
                receipt=f"rc{week}{i}", cost_usd=0.02)
            broken = week == 2 and mid == "m:quotes"
            if broken:
                add("mission.blocked", f"{day}{i + 1}T10:05:00Z", mission_id=mid, reason="assessment contract violation")
            else:
                add("mission.achieved", f"{day}{i + 1}T10:10:00Z", mission_id=mid)
            add("mission.appraised", f"{day}{i + 1}T10:20:00Z", mission_id=mid, capability=cap,
                verdict="REFUTED" if broken else "VERIFIED")
    return ev


def exercise(root) -> dict:
    ev = sample_events()
    split = "2026-09-10T00:00:00Z"
    return {"trace_m_quotes": [s["kind"] for s in correlate(ev, "m:quotes")["missions"]["m:quotes"]["spans"]][:6],
            "week1": metrics(ev, end=split), "week2": metrics(ev, start=split),
            "why_closures_fell": why_changed(ev, "closures", split=split),
            "why_verified_rate_fell": why_changed(ev, "verified_rate", split=split)["drivers"][:1],
            "why_latency_rose": why_changed(ev, "decision_latency_s", split=split)["drivers"][:1],
            "otel_span_count": len(otel_spans(ev)), "otel_first": otel_spans(ev)[0]["name"]}
