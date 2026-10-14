"""#50 Rabbit Hole Engine: route a person from curiosity to depth, owned ground and offers, by observed behavior.

Recombines two existing mechanisms that each lacked the other:

  foundry/territory.py (Kernel)   an evidence-gated DAG of content with exactly one
                                  owned exit; weak, stale or retired nodes cannot publish
  WMI rabbit_hole.py              earned progression (only from consumed nodes), a bounded
                                  session depth, and an exit ramp on every recommendation

and adds the missing half: *observed behavior*. Every visitor step is recorded
(consume, complete, leave, join, buy). Routing at a fork prefers the door that,
for visitors who took it from this node, most often led to a completed next
step or owned ground (Laplace-smoothed, so new doors are tried, not starved).
Doors leading to nodes that cannot publish are never offered.

The ethics are structural, carried from both sources: a node declares what it
is; prohibited patterns refuse it; depth is capped per session; leaving is
always one step and never punished; nothing is withheld to force a step.
The observation log is the input the #34 attribution engine measures.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

PROHIBITED = ("artificial scarcity", "false urgency", "hidden cost", "guaranteed income", "risk-free", "act now",
              "secret they don't want", "engagement bait")
MAX_SESSION_DEPTH = 6
STEP_KINDS = ("consume", "complete", "leave", "join", "buy")


class RabbitHoleError(ValueError):
    pass


def _load(root: Path) -> dict:
    p = Path(root) / "territory.json"
    return json.loads(p.read_text()) if p.exists() else {"nodes": {}, "entry": None, "steps": [], "sessions": {}}


def _save(root: Path, state: dict) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    tmp = Path(root) / "territory.tmp"
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(Path(root) / "territory.json")


def _validate_node(node: dict) -> list[str]:
    problems = []
    for f in ("node_id", "question", "declares", "value_offered", "depth"):
        if node.get(f) in (None, ""):
            problems.append(f"node missing {f}")
    text = f"{node.get('question', '')} {node.get('body', '')} {node.get('value_offered', '')}".lower()
    problems += [f"prohibited pattern {p!r}" for p in PROHIBITED if p in text]
    if not 0.0 <= float(node.get("evidence_level", 0)) <= 1.0:
        problems.append("evidence_level outside [0,1]")
    if node.get("owned_exit") and not node.get("owned_ground"):
        problems.append("an owned exit must name owned ground")
    return problems


def add_node(root: Path, node: dict, *, entry: bool = False) -> dict:
    problems = _validate_node(node)
    if problems:
        raise RabbitHoleError(f"node refused: {problems}")
    state = _load(root)
    if node["node_id"] in state["nodes"]:
        raise RabbitHoleError(f"duplicate node {node['node_id']}")
    state["nodes"][node["node_id"]] = {**node, "retired": False, "next_doors": list(node.get("next_doors", []))}
    if entry:
        if state["entry"]:
            raise RabbitHoleError("a territory has one entry")
        state["entry"] = node["node_id"]
    _save(root, state)
    return {"node_id": node["node_id"], "entry": entry}


def retire(root: Path, node_id: str, *, reason: str) -> dict:
    state = _load(root)
    state["nodes"][node_id]["retired"] = True
    state["nodes"][node_id]["retired_reason"] = reason
    _save(root, state)
    return {"node_id": node_id, "retired": True}


def validate(root: Path) -> list[str]:
    """Territory-level invariants, from foundry/territory.py: reachable, acyclic, one owned exit."""
    state = _load(root)
    nodes = state["nodes"]
    problems = []
    if not state["entry"]:
        return ["no entry node"]
    for n in nodes.values():
        for d in n["next_doors"]:
            if d not in nodes:
                problems.append(f"{n['node_id']} opens a door to nowhere: {d}")
    seen, stack = set(), [state["entry"]]
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in nodes:
            continue
        seen.add(cur)
        stack.extend(nodes[cur]["next_doors"])
    if set(nodes) - seen:
        problems.append(f"unreachable: {sorted(set(nodes) - seen)}")
    color = {k: 0 for k in nodes}

    def cyc(k):
        color[k] = 1
        for d in nodes[k]["next_doors"]:
            if d in color and (color[d] == 1 or (color[d] == 0 and cyc(d))):
                return True
        color[k] = 2
        return False
    if any(color[k] == 0 and cyc(k) for k in nodes):
        problems.append("cycle: depth must descend")
    exits = [n for n in nodes.values() if n.get("owned_exit")]
    if len(exits) != 1:
        problems.append(f"exactly one owned exit required; found {len(exits)}")
    return problems


def publishable(node: dict, now: str) -> tuple[bool, str]:
    if node["retired"]:
        return False, "retired"
    if node.get("expires_at") and now >= node["expires_at"]:
        return False, "evidence expired"
    if float(node.get("evidence_level", 0)) < 0.7:
        return False, f"evidence {node.get('evidence_level')} below publish floor 0.7"
    return True, "ok"


def observe(root: Path, *, session: str, kind: str, node_id: str, at: str) -> dict:
    """What a visitor actually did. Recommendations follow consumption; they never precede it."""
    if kind not in STEP_KINDS:
        raise RabbitHoleError(f"unknown step kind {kind}")
    state = _load(root)
    if node_id not in state["nodes"]:
        raise RabbitHoleError(f"unknown node {node_id}")
    sess = state["sessions"].setdefault(session, {"path": [], "ended": False})
    if sess["ended"]:
        raise RabbitHoleError("session already left")
    prev = sess["path"][-1] if sess["path"] else None
    state["steps"].append({"session": session, "kind": kind, "node": node_id, "from": prev, "at": at})
    if kind == "consume":
        sess["path"].append(node_id)
    if kind in ("leave", "join", "buy"):
        sess["ended"] = True
    _save(root, state)
    return {"session": session, "depth": len(sess["path"])}


def _door_outcomes(state: dict) -> dict[tuple, dict]:
    """For each (from, door): how often taking that door led to completion, owned ground, or leaving."""
    out = defaultdict(lambda: {"taken": 0, "completed": 0, "owned": 0, "good": 0, "left": 0})
    by_session = defaultdict(list)
    for s in state["steps"]:
        by_session[s["session"]].append(s)
    for steps in by_session.values():
        for i, s in enumerate(steps):
            if s["kind"] != "consume" or s["from"] is None:
                continue
            key = (s["from"], s["node"])
            out[key]["taken"] += 1
            later = steps[i + 1:]
            completed = any(t["kind"] == "complete" and t["node"] == s["node"] for t in later)
            owned = any(t["kind"] in ("join", "buy") for t in later)
            out[key]["completed"] += completed
            out[key]["owned"] += owned
            out[key]["good"] += completed or owned          # one visitor counts once, however well it went
            nxt = next((t for t in later if t["kind"] != "complete"), None)
            if nxt is not None and nxt["kind"] == "leave":
                out[key]["left"] += 1
    return out


def door_value(stats: dict | None) -> float:
    """Laplace-smoothed share of door-takers who completed or reached owned ground; new doors start at 0.5."""
    if not stats:
        return 0.5
    return (stats["good"] + 1) / (stats["taken"] + 2)


def recommend(root: Path, *, session: str, now: str) -> dict:
    state = _load(root)
    nodes = state["nodes"]
    sess = state["sessions"].get(session, {"path": [], "ended": False})
    exit_ramp = "leave now; everything so far stands alone and nothing is withheld"
    if sess["ended"]:
        return {"node": None, "why": "session ended", "exit_ramp": exit_ramp}
    if len(sess["path"]) >= MAX_SESSION_DEPTH:
        return {"node": None, "why": f"depth ceiling {MAX_SESSION_DEPTH}: the honest next step is to stop", "exit_ramp": exit_ramp}
    if not sess["path"]:
        if not state["entry"]:
            return {"node": None, "why": "no territory published yet", "exit_ramp": exit_ramp}
        entry = nodes[state["entry"]]
        ok, why = publishable(entry, now)
        return {"node": state["entry"] if ok else None, "why": "entry" if ok else f"entry unpublishable: {why}",
                "exit_ramp": exit_ramp}
    current = nodes[sess["path"][-1]]
    if current.get("owned_exit"):
        return {"node": None, "owned_ground": current["owned_ground"], "why": "owned ground reached; the next step is the offer",
                "exit_ramp": exit_ramp}
    stats = _door_outcomes(state)
    candidates = []
    for door in current["next_doors"]:
        n = nodes[door]
        ok, why = publishable(n, now)
        if not ok or door in sess["path"] or n["depth"] <= current["depth"]:
            continue
        candidates.append((door_value(stats.get((current["node_id"], door))), -n["depth"], door))
    if not candidates:
        return {"node": None, "why": "frontier exhausted; no honest deeper step", "exit_ramp": exit_ramp}
    candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
    value, _, door = candidates[0]
    return {"node": door, "why": f"observed door value {value:.2f} from {current['node_id']}",
            "alternatives": [c[2] for c in candidates[1:]], "exit_ramp": exit_ramp}


QUERY_OPS = {"recommend": lambda a, r: recommend(r, session=a["session"], now=a["now"]),
             "validate": lambda a, r: {"problems": validate(r)},
             "doors": lambda a, r: {f"{k[0]}->{k[1]}": v for k, v in sorted(_door_outcomes(_load(r)).items())}}
APPLY_OPS = {"add_node": lambda a, r: add_node(r, a["node"], entry=bool(a.get("entry"))),
             "retire": lambda a, r: retire(r, a["node_id"], reason=a["reason"]),
             "observe": lambda a, r: observe(r, session=a["session"], kind=a["kind"], node_id=a["node_id"], at=a["at"])}


def demo_territory(root: Path) -> None:
    def node(nid, q, depth, doors=(), **kw):
        return {"node_id": nid, "question": q, "declares": "educational article by a disclosed synthetic author",
                "value_offered": f"a working method for {q.lower()}", "depth": depth, "evidence_level": kw.pop("ev", 0.9),
                "next_doors": list(doors), **kw}
    add_node(root, node("why-proof", "Why do suppliers wait 60 days to be paid?", 0, ["pod-basics", "disputes"]), entry=True)
    add_node(root, node("pod-basics", "What counts as proof of delivery?", 1, ["audit-kit"]))
    add_node(root, node("disputes", "How do delivery disputes actually get resolved?", 1, ["audit-kit", "weak"]))
    add_node(root, node("weak", "Unverified claim about dispute rates", 2, ev=0.4))
    add_node(root, node("audit-kit", "Run your own delivery audit", 2, ["offer"]))
    add_node(root, node("offer", "Get audits run for you", 3, owned_exit=True, owned_ground="portal:/portal/<customer>/"))


def exercise(root) -> dict:
    root = Path(root)
    now = "2026-10-13T12:00:00Z"
    demo_territory(root)
    problems = validate(root)
    refusals = {}
    try:
        add_node(root, {"node_id": "bait", "question": "Act now: the secret they don't want you to see", "declares": "x",
                        "value_offered": "y", "depth": 1, "evidence_level": 0.9})
    except RabbitHoleError as exc:
        refusals["dark_pattern"] = str(exc)[:70]
    # observed behavior: visitors who go why-proof -> disputes mostly leave; those who go -> pod-basics complete and buy
    t = 0
    for i in range(6):
        s = f"v{i}"
        observe(root, session=s, kind="consume", node_id="why-proof", at=f"{now[:-1]}{t:02d}"); t += 1
        door = "pod-basics" if i % 3 else "disputes"
        observe(root, session=s, kind="consume", node_id=door, at=now)
        if door == "pod-basics":
            observe(root, session=s, kind="complete", node_id=door, at=now)
            observe(root, session=s, kind="consume", node_id="audit-kit", at=now)
            observe(root, session=s, kind="consume", node_id="offer", at=now)
            observe(root, session=s, kind="buy", node_id="offer", at=now)
        else:
            observe(root, session=s, kind="leave", node_id=door, at=now)
    observe(root, session="new", kind="consume", node_id="why-proof", at=now)
    routed = recommend(root, session="new", now=now)
    observe(root, session="new", kind="consume", node_id="disputes", at=now)
    from_disputes = recommend(root, session="new", now=now)      # 'weak' (evidence 0.4) is never offered
    deep = "deep"
    for nid in ("why-proof", "pod-basics", "audit-kit", "offer"):
        observe(root, session=deep, kind="consume", node_id=nid, at=now)
    at_exit = recommend(root, session=deep, now=now)
    capped = "cap"
    for nid in ("why-proof", "pod-basics", "audit-kit", "offer"):
        observe(root, session=capped, kind="consume", node_id=nid, at=now)
    import json as _json
    st = _load(root)
    st["sessions"][capped]["path"] += ["offer"] * (MAX_SESSION_DEPTH - 4)   # a visitor at the ceiling
    _save(root, st)
    at_cap = recommend(root, session=capped, now=now)
    doors = {f"{k[0]}->{k[1]}": v for k, v in sorted(_door_outcomes(_load(root)).items())}
    return {"territory_valid": problems == [], "refusals": refusals,
            "routed_from_entry": routed["node"], "routed_why": routed["why"], "alternatives": routed.get("alternatives"),
            "weak_node_never_offered": from_disputes["node"] != "weak" and "weak" not in (from_disputes.get("alternatives") or []),
            "from_disputes": from_disputes["node"], "owned_ground": at_exit.get("owned_ground"),
            "exit_ramp_always_present": all("exit_ramp" in r for r in (routed, from_disputes, at_exit, at_cap)),
            "depth_cap_stops": at_cap["node"] is None and "ceiling" in at_cap["why"],
            "door_stats": doors}
