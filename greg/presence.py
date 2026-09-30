"""Body presence: was GREG actually running, measured from retained history.

A mission is durable across absence; the body is not always present. The founder's
first body is a Chromebook: ChromeOS kills Linux processes at logout and, by design,
never restarts the Linux VM at login, and a closed lid suspends it. A Mac or laptop
sleeps too. "Persistent operation" therefore has to be measured and reported, never
implied by a clean morning report.

Evidence used (no new store, no periodic ledger writes):

* ``body.booted`` carries ``previous_heartbeat``: the heartbeat file the previous
  process rewrote atomically every tick. It survives SIGKILL, power loss and a killed
  VM, so the absence between two processes is bounded to one tick.
* ``body.gap_observed`` is recorded by a running body when its wall clock advanced
  far more than its monotonic clock between two loop turns: the host was suspended
  (Linux CLOCK_MONOTONIC and macOS mach_absolute_time do not count sleep). When both
  clocks advanced the process itself was stalled.
* ``body.stopped`` / ``body.stop_persisted`` separate a deliberate founder stop (not
  counted against availability) from an OS stop, logout or crash (counted).
* ``mission.schedule`` / ``mission.observed`` show which due observations fell inside
  an absence: the cost of absence in mission terms.

A sustained shortfall becomes ONE founder decision request with alternatives. It is
argued from mission lateness, never from the body's own continuation: pause, stop and
replacement stay legitimate, and nothing here buys, rents or enrolls anything.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from greg.journal import Journal, iso
from provenance.ledger import sha256_json

SUSPEND_MIN_SECONDS = 60           # wall clock ahead of monotonic by this much: the host slept
STALL_MIN_SECONDS = 600            # both clocks advanced this much in one loop turn: the process stalled
LATE_TOLERANCE_SECONDS = 120       # a due observation this late is late, not jitter
AVAILABILITY_THRESHOLD = 0.75
REVIEW_WINDOW = timedelta(hours=72)
MIN_HISTORY = timedelta(hours=24)
DELIBERATE = "deliberate_stop"


def _t(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:   # a naive time cannot be compared with the body's clock
        raise ValueError(f"timestamp without a timezone: {value!r}")
    return parsed


def note_gap(journal: Journal, boot_id: str, previous: tuple[datetime, float], current: tuple[datetime, float]):
    """Record a suspension or stall observed by the running body between two loop turns."""
    wall = (current[0] - previous[0]).total_seconds()
    mono = current[1] - previous[1]
    if wall < 0:
        return None     # the wall clock stepped back; greg.missions already re-observes on repeats
    if wall - mono >= SUSPEND_MIN_SECONDS:
        cause = "host_suspended"
    elif mono >= STALL_MIN_SECONDS:
        cause = "process_stalled"
    else:
        return None
    record = {"boot_id": boot_id, "from": iso(previous[0]), "to": iso(current[0]), "cause": cause,
              "wall_seconds": round(wall, 3), "monotonic_seconds": round(mono, 3),
              "evidence": "wall clock advanced while the monotonic clock did not" if cause == "host_suspended"
              else "both clocks advanced: the process ran no loop turn"}
    return journal.record("body.gap_observed", record, key=[boot_id, record["from"], record["to"]])


def previous_heartbeat(heartbeat: dict | None) -> dict | None:
    """The part of the last heartbeat file worth keeping as boot evidence (unsigned, local)."""
    if not isinstance(heartbeat, dict) or not isinstance(heartbeat.get("at"), str):
        return None
    try:
        _t(heartbeat["at"])
    except ValueError:
        return None
    return {"boot_id": heartbeat.get("boot_id"), "at": heartbeat["at"], "state": heartbeat.get("state"),
            "source": "heartbeat file (unsigned, written by the previous process)"}


def _clip(start: datetime, end: datetime, lo: datetime, hi: datetime) -> float:
    return max(0.0, (min(end, hi) - max(start, lo)).total_seconds())


def summary(journal: Journal, *, now: datetime, since: datetime | None = None,
            heartbeat: dict | None = None) -> dict:
    """Presence of the body over [since, now] from retained history.

    ``heartbeat`` is the current heartbeat file, used only to end an unfinished last
    boot whose process is no longer reporting (e.g. read after a crash).
    """
    heartbeat = previous_heartbeat(heartbeat)   # an unreadable or naive heartbeat is not evidence
    boots = [e.payload for e in journal.replay("body.booted")]
    if not boots:
        return {"reality_status": "RETAINED_EVIDENCE_PROJECTION", "boots": 0, "state": "NEVER_STARTED",
                "availability": None, "absences": [], "late_observations": []}
    stopped = {e.payload["boot_id"]: e.payload for e in journal.replay("body.stopped")}
    founder_stops = [_t(e.payload["at"]) for e in journal.replay("body.stop_persisted")]
    gaps = [e.payload for e in journal.replay("body.gap_observed")]
    first = _t(boots[0]["at"])
    lo = max(since, first) if since else first
    absences, present = [], 0.0
    for i, boot in enumerate(boots):
        start = _t(boot["at"])
        nxt = boots[i + 1] if i + 1 < len(boots) else None
        stop = stopped.get(boot["boot_id"])
        uncertain = False
        if stop:
            end = _t(stop["at"])
        elif nxt and (nxt.get("previous_heartbeat") or {}).get("boot_id") == boot["boot_id"]:
            end = _t(nxt["previous_heartbeat"]["at"])
        elif nxt:
            end, uncertain = start, True          # no evidence of how long it ran: count none of it
        elif heartbeat and heartbeat.get("boot_id") == boot["boot_id"] and heartbeat.get("state") != "STOPPED" \
                and (now - _t(heartbeat["at"])).total_seconds() > LATE_TOLERANCE_SECONDS:
            end = _t(heartbeat["at"])
            absences.append({"from": iso(end), "to": None, "cause": "not_reporting", "counts": True,
                             "seconds": round(_clip(end, now, lo, now), 3),
                             "detail": "the last process stopped writing its heartbeat and recorded no stop"})
        else:
            end = now
        end = max(end, start)
        inner = [g for g in gaps if g["boot_id"] == boot["boot_id"]]
        present += _clip(start, end, lo, now) - sum(_clip(_t(g["from"]), _t(g["to"]), lo, now) for g in inner)
        for g in inner:
            absences.append({"from": g["from"], "to": g["to"], "cause": g["cause"], "counts": True,
                             "seconds": round(_clip(_t(g["from"]), _t(g["to"]), lo, now), 3)})
        if nxt is not None:
            if stop and ("STOP file" in stop.get("reason", "")
                         or any(start <= s <= end for s in founder_stops)):
                cause = DELIBERATE
            elif stop:
                cause = "os_stop_or_shutdown"     # SIGTERM: logout, VM or OS shutdown, or a service stop
            else:
                cause = "process_lost"            # SIGKILL, crash, power loss or a killed VM
            absences.append({"from": iso(end), "to": nxt["at"], "cause": cause, "counts": cause != DELIBERATE,
                             "seconds": round(_clip(end, _t(nxt["at"]), lo, now), 3),
                             **({"end_uncertain": True} if uncertain else {})})
    in_window = [a for a in absences if a["seconds"] > 0]
    deliberate = sum(a["seconds"] for a in in_window if not a["counts"])
    eligible = (now - lo).total_seconds() - deliberate
    late = late_observations(journal, [a for a in in_window if a["counts"]], now=now)
    last_boot = boots[-1]
    state = ("STOPPED" if last_boot["boot_id"] in stopped else
             "NOT_REPORTING" if any(a["cause"] == "not_reporting" for a in absences) else "RUNNING")
    return {
        "reality_status": "RETAINED_EVIDENCE_PROJECTION",
        "window": {"from": iso(lo), "to": iso(now)},
        "state": state, "boots": len(boots),
        "present_seconds": round(max(0.0, present), 3),
        "absent_seconds": round(sum(a["seconds"] for a in in_window if a["counts"]), 3),
        "deliberately_stopped_seconds": round(deliberate, 3),
        "availability": round(max(0.0, min(1.0, present / eligible)), 4) if eligible > 0 else None,
        "absences": in_window,
        "late_observations": late,
        "limits": "bounded by one tick for process death; host sleep is detected from clock divergence; "
                  "the heartbeat file is unsigned local evidence; nothing here proves who used the computer",
    }


def late_observations(journal: Journal, absences: list, *, now: datetime) -> list:
    """Due mission observations that fell inside a counted absence, and how late they ran."""
    windows = [(_t(a["from"]), _t(a["to"]) if a["to"] else now) for a in absences]
    observed = {}
    for e in journal.replay("mission.observed"):
        observed.setdefault(e.payload["mission_id"], []).append(_t(e.payload["at"]))
    late, seen = [], set()
    for e in journal.replay("mission.schedule"):
        mid, due = e.payload["mission_id"], _t(e.payload["next_observe_at"])
        if (mid, due) in seen or due > now or not any(a <= due < b for a, b in windows):
            continue
        seen.add((mid, due))
        after = sorted(t for t in observed.get(mid, []) if t >= due)
        lateness = ((after[0] if after else now) - due).total_seconds()
        if lateness > LATE_TOLERANCE_SECONDS:
            late.append({"mission_id": mid, "due": iso(due), "observed": iso(after[0]) if after else None,
                         "late_seconds": round(lateness, 3)})
    return late


def recommend(journal: Journal, *, now: datetime, platform_hint: str | None = None) -> dict | None:
    """A sustained availability shortfall that made missions late -> ONE founder decision request."""
    boots = journal.replay("body.booted")
    if not boots or now - _t(boots[0].payload["at"]) < MIN_HISTORY:
        return None
    found = summary(journal, now=now, since=now - REVIEW_WINDOW)
    if found["availability"] is None or found["availability"] >= AVAILABILITY_THRESHOLD \
            or not found["late_observations"]:
        return None
    answered = {e.payload["request_id"] for e in journal.replay("decision.")
                if e.type in ("greg.decision.answered", "greg.decision.withdrawn")}
    if any(e.payload.get("kind") == "BODY_AVAILABILITY" and e.payload["request_id"] not in answered
           for e in journal.replay("decision.requested")):
        return None
    week = now.isocalendar()
    request_id = "req-presence-" + sha256_json({"kind": "BODY_AVAILABILITY", "week": [week[0], week[1]]})[7:23]
    if any(e.payload["request_id"] == request_id for e in journal.replay("decision.requested")):
        return None
    worst = max(found["late_observations"], key=lambda x: x["late_seconds"])
    keep_present = ("keep this computer signed in, charging and awake during mission hours; on a Chromebook, "
                    "open the Linux terminal after every restart or login (no spend)"
                    if platform_hint == "chromeos" else
                    "keep this computer signed in, powered and awake during mission hours (no spend)")
    message = {
        "request_id": request_id, "mission_id": None, "kind": "BODY_AVAILABILITY", "action_id": None,
        "scope_digest": sha256_json({"window": found["window"], "availability": found["availability"]}),
        "why_now": (f"the body was present {found['availability']:.0%} of the last "
                    f"{int(REVIEW_WINDOW.total_seconds() // 3600)}h outside deliberate stops; "
                    f"{len(found['late_observations'])} due observation(s) ran late, worst "
                    f"{worst['late_seconds'] / 3600:.1f}h ({worst['mission_id']})"),
        "recommendation": "first try the two no-spend options; if availability stays below "
                          f"{AVAILABILITY_THRESHOLD:.0%} with late observations, ask GREG for a bounded "
                          "read-only research mission comparing always-on hardware you would own",
        "alternatives": [keep_present,
                         "match mission cadence to measured availability; missions stay durable and run late (no spend)",
                         "an always-on computer you own, enrolled as its own body (capital purchase; your installation)",
                         "a rented always-on host (metered; not hardware you own; data and credentials leave this computer)",
                         "do nothing: missions resume late when the body returns"],
        "authority_requested": {"spend": "none requested; any purchase, rental or enrollment is a separate founder decision"},
        "argued_from": "mission lateness measured from retained history; never the body's own continuation",
        "consequence_of_no_response": "missions stay durable and resume late; nothing is bought, rented or enrolled",
        "evidence": {"availability": found["availability"], "absences": found["absences"][-10:],
                     "late_observations": found["late_observations"][-10:]},
        "created_at": iso(now), "reality_status": "RECORDED_LOCAL_MESSAGE",
        "uncertainty": "availability is measured on this body only; future use patterns may differ",
    }
    journal.record("decision.requested", message, key=request_id)
    return message
