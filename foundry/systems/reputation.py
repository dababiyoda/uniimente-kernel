"""#41 Reputation from verified outcomes, operating conditions, incidents and recovery.

Only declared outcome records carrying an evidence reference enter this
conditional arithmetic. A reference's existence does not authenticate its
content or verdict. The canonical GREG outcome/learning plane owns verified
records and any permitted routing update; this module does not update it.
Each subject in a context gets a Beta posterior over success; ranking
uses the conservative lower bound, so one lucky success cannot outrank a long
record. Older outcomes decay by half-life; an incident weighs more than an
ordinary failure unless a verified recovery follows it. Fewer than
``MIN_EVIDENCE`` effective outcomes is reported as ``insufficient``, not as a
score.
"""
from __future__ import annotations

import math
from datetime import datetime

MIN_EVIDENCE = 3.0
INCIDENT_WEIGHT = 3.0
RECOVERED_INCIDENT_WEIGHT = 1.0
Z = 1.2816  # one-sided 90% lower bound


def _age_days(at: str, now: str) -> float:
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    return max(0.0, (parse(now) - parse(at)).total_seconds() / 86400)


def score(records: list[dict], *, now: str, half_life_days: float = 90.0) -> dict:
    if type(half_life_days) not in (int, float) or not math.isfinite(half_life_days) or half_life_days <= 0:
        raise ValueError("half-life must be positive and finite")
    table: dict[tuple, dict] = {}
    ignored = 0
    for r in records:
        if not r.get("evidence") or r.get("verdict") not in ("VERIFIED", "REFUTED"):
            ignored += 1
            continue
        weight = 0.5 ** (_age_days(r["at"], now) / half_life_days)
        row = table.setdefault((r["subject"], r.get("context", "*")), {"success": 0.0, "failure": 0.0, "incidents": 0})
        if r["verdict"] == "VERIFIED":
            row["success"] += weight
        else:
            if r.get("incident"):
                row["incidents"] += 1
                weight *= RECOVERED_INCIDENT_WEIGHT if r.get("recovered") else INCIDENT_WEIGHT
            row["failure"] += weight
    out = []
    for (subject, context), row in sorted(table.items()):
        a, b = 1 + row["success"], 1 + row["failure"]
        n = a + b
        mean = a / n
        lower = max(0.0, mean - Z * math.sqrt(mean * (1 - mean) / (n + 1)))
        evidence = row["success"] + row["failure"]
        out.append({"subject": subject, "context": context, "mean": round(mean, 4), "lower_bound": round(lower, 4),
                    "effective_outcomes": round(evidence, 3), "incidents": row["incidents"],
                    "status": "rated" if evidence >= MIN_EVIDENCE else "insufficient"})
    ranked = sorted((r for r in out if r["status"] == "rated"), key=lambda r: (-r["lower_bound"], r["subject"]))
    return {"subjects": out, "ranking": [r["subject"] + "@" + r["context"] for r in ranked], "ignored_unevidenced": ignored,
            "evidence_scope": "conditional arithmetic over supplied records; references are not authenticated",
            "authority_created": False, "routing_updated": False}


def from_greg(events) -> list[dict]:
    """Capability outcome records from GREG: each appraised closure credits the capabilities it used."""
    used: dict[str, set] = {}
    records = []
    for e in events:
        kind, p = e["type"].removeprefix("greg."), e["payload"]
        if kind == "mission.action" and p.get("status") == "DONE":
            used.setdefault(p["mission_id"], set()).add(p["capability"])
        elif kind == "mission.appraised" and p.get("world_reobserved") is True:
            for capability in sorted(used.get(p["mission_id"], ())):
                records.append({"subject": capability, "context": "greg", "verdict": p["verdict"],
                                "at": e.get("at") or p.get("at") or "1970-01-01T00:00:00Z",
                                "evidence": [e["event_id"]], "incident": p["verdict"] == "REFUTED"})
    return records


QUERY_OPS = {"score": lambda a, r: score(a["records"], now=a["now"], half_life_days=float(a.get("half_life_days", 90)))}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    now = "2026-09-27T00:00:00Z"
    ev = ["receipt"]
    rec = lambda s, v, at="2026-09-20T00:00:00Z", **k: {"subject": s, "context": "delivery", "verdict": v, "at": at, "evidence": ev, **k}
    records = ([rec("steady", "VERIFIED") for _ in range(9)] + [rec("steady", "REFUTED")] +
               [rec("lucky", "VERIFIED", at=now) for _ in range(3)] +
               [rec("incident", "VERIFIED") for _ in range(8)] + [rec("incident", "REFUTED", incident=True)] +
               [rec("recovered", "VERIFIED") for _ in range(8)] + [rec("recovered", "REFUTED", incident=True, recovered=True)] +
               [rec("stale", "VERIFIED", at="2024-01-01T00:00:00Z") for _ in range(9)] +
               [{"subject": "sybil", "context": "delivery", "verdict": "VERIFIED", "at": now, "evidence": []} for _ in range(50)])
    out = score(records, now=now)
    by = {r["subject"]: r for r in out["subjects"]}
    return {"ranking": out["ranking"], "steady_beats_lucky": out["ranking"].index("steady@delivery") < out["ranking"].index("lucky@delivery"),
            "recovery_beats_unrecovered": by["recovered"]["lower_bound"] > by["incident"]["lower_bound"],
            "stale_is_insufficient": by["stale"]["status"] == "insufficient",
            "sybil_ignored": out["ignored_unevidenced"] == 50 and "sybil" not in by}
