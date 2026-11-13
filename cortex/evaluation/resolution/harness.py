"""Abstention-to-resolution routing: the arm harness (pre-registered 2026-11-13).

Runs one suite item as a signed mission on a real GREG Body of the tree under test, lets one simulated founder take
at most one signed action after three ticks, runs three more ticks, and records what happened. The tree is chosen at
run time (``--tree``), so the same frozen file measures B0, the prerequisites and the dividend; it imports nothing
from any tree before ``--tree`` is on ``sys.path``.

    python harness.py --tree TREE --suite FILE --policy standard|parser|none --out FILE [--ablate consumer|producer]

Contract the dividend is measured against, fixed here before its code exists:

* an open ask (``decision.requested``) may carry ``prepared_command``:
  ``{"kind": <founder command kind>, "body": {...}, "founder_supplies": [{"path": [...], "from": <key>}]}``;
  the standard founder fills each ``path`` in ``body`` with the value the perturbation removed under ``from``,
  signs ``kind`` with that ``body`` and nothing else;
* the consumer ablation replaces ``greg.missions.MissionEngine._resolution_ask`` with one that returns None;
* the producer ablation replaces ``greg.cognition.resolution.read`` with one that returns None.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

TICKS = 3
ADVANCE_S = 31
PART_KEYS = ("formal_model", "estimation_model", "schedule_request", "deterrence_model", "claim", "causal_spec",
             "sources", "evidence", "options", "factors", "variables", "constraints", "objective")
_TREE = None
_ABLATE = None


def _enter(tree: str, ablate: str | None) -> None:
    """Import the tree under test, then apply the declared ablation. Called once per process."""
    global _TREE, _ABLATE
    _TREE, _ABLATE = tree, ablate
    os.chdir(tree)
    sys.path.insert(0, tree)
    if ablate == "consumer":
        import greg.missions as missions
        if not hasattr(missions.MissionEngine, "_resolution_ask"):
            raise SystemExit("ARM_INVALID: the consumer ablation names greg.missions.MissionEngine._resolution_ask")
        missions.MissionEngine._resolution_ask = lambda self, *a, **k: None
    elif ablate == "producer":
        import greg.cognition.resolution as resolution
        if not hasattr(resolution, "read"):
            raise SystemExit("ARM_INVALID: the producer ablation names greg.cognition.resolution.read")
        resolution.read = lambda *a, **k: None
    elif ablate is not None:
        raise SystemExit(f"unknown ablation {ablate!r}")


# ------------------------------------------------------------------ missions
def _request(item: dict) -> dict:
    pid = item["item_id"]
    if item["wrap"] == "problem":
        return {"problem_id": pid, "problem": {"question": item["question"], "payload": copy.deepcopy(item["payload"])}}
    return {"problem_id": pid, "compile": {"geometry": copy.deepcopy(item["geometry"]),
                                           "data": copy.deepcopy(item["data"])}}


def _spec(item: dict, request: dict, mission_id: str) -> dict:
    from tests.greg_fixtures import mission
    from greg.templates import compiled_question
    if "compile" in request:
        spec = compiled_question(problem_id=request["problem_id"], data=request["compile"]["data"],
                                 geometry=request["compile"]["geometry"])
        spec["mission_id"] = mission_id
        return spec
    params = request
    return mission(mission_id, checks=[{"check_id": "answered", "description": "the question is answered",
                                        "sensor": {"capability": "cognition.solve", "target": "cognition:resolution",
                                                   "params": params},
                                        "predicate": {"op": "equals", "field": "abstention_state", "value": "NONE"}}],
                   strategies=[{"action_id": "solve", "capability": "cognition.solve",
                                "target": "cognition:resolution", "params": params, "advances": ["answered"],
                                "rationale": "answer the question"}],
                   capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="internal_write")


def _mission_id(item: dict, suffix: str = "") -> str:
    return ("m:" + re.sub(r"[^a-z0-9-]", "-", item["item_id"]) + suffix)[:90]


def _with_request(spec: dict, request: dict, mission_id: str) -> dict:
    """A successor: the original signed spec, a new id, every step's request replaced; nothing else changes."""
    out = copy.deepcopy(spec)
    out["mission_id"] = mission_id
    for step in [*(s.get("sensor") for s in out.get("success_checks") or out.get("checks") or []),
                 *(out.get("strategies") or [])]:
        if step and step.get("capability") == "cognition.solve":
            step["params"] = copy.deepcopy(request)
    return out


# ------------------------------------------------------------------ observation
def _state(body, mid: str) -> dict:
    m = body.engine.book.missions.get(mid)
    return {"status": getattr(m, "status", None) if m else None}


def _appraised(body, mid: str) -> list:
    return [e.payload.get("verdict") for e in body.journal.replay("mission.appraised")
            if e.payload.get("mission_id") == mid]


def _asks(body, mid: str) -> list:
    answered = {e.payload.get("request_id") for e in body.journal.replay("decision.answered")}
    out = []
    for e in body.journal.replay("decision.requested"):
        p = e.payload
        if p.get("mission_id") == mid:
            out.append({"request_id": p.get("request_id"), "kind": p.get("kind"),
                        "recommendation": str(p.get("recommendation", ""))[:400],
                        "prepared_command": p.get("prepared_command"), "open": p.get("request_id") not in answered})
    return out


def _genesis(body, mid: str) -> list:
    return [e.payload.get("function") for e in body.journal.replay("deficit.opened")
            if e.payload.get("mission_id") == mid]


def _outputs(body) -> list:
    out = []
    for r in body.ledger.by_type("receipt"):
        o = (r.payload.get("result") or {}).get("output")
        if isinstance(o, dict):
            out.append(o)
    return out


def _usable(body, cid: str) -> bool:
    try:
        return bool(body.registry.usable(cid)[0])
    except Exception:  # noqa: BLE001 - an unknown capability is not usable
        return False


def _harm(item: dict, body, achieved: bool) -> bool:
    if not achieved or item.get("harm") is None:
        return False
    if item["harm"] in ("protection", "dependency"):
        return True
    return any(not _usable(body, cid) for cid in item["detach"])     # "detached": a part's only readers withheld


# ------------------------------------------------------------------ founders
def _fill(body: dict, supplies: list, removed: dict) -> dict | None:
    body = copy.deepcopy(body)
    for s in supplies or []:
        if s.get("from") not in removed or not isinstance(s.get("path"), list) or not s["path"]:
            return None
        node = body
        for key in s["path"][:-1]:
            node = node.setdefault(key, {})
        node[s["path"][-1]] = copy.deepcopy(removed[s["from"]])
    return body


def standard_founder(body, item, mid, spec) -> dict | None:
    asks = [a for a in _asks(body, mid) if a["open"]]
    for a in asks:
        pc = a["prepared_command"]
        if isinstance(pc, dict) and isinstance(pc.get("body"), dict) and pc.get("kind"):
            filled = _fill(pc["body"], pc.get("founder_supplies"), item["removed"])
            if filled is not None:
                return {"kind": pc["kind"], "body": filled, "source": "prepared_command"}
    for a in asks:
        m = re.search(r"greg attach ([a-z0-9_.:-]+)", a["recommendation"])
        if m:
            return {"kind": "CAPABILITY_ATTACH", "body": {"capability_id": m.group(1)}, "source": "attach_recommendation"}
    return None


def parser_founder(body, item, mid, spec) -> dict | None:
    """S: a capable founder reading the raw receipt with today's code (rules fixed in the pre-registration)."""
    outputs = _outputs(body)
    if not outputs:
        return None
    last = outputs[-1]
    strings = [s for s in _strings(last)]
    try:
        from greg.cognition.bridge import ORGANS
    except ImportError:
        ORGANS = {}
    for s in strings:                                                  # (1) a withheld or detached capability
        if "withheld by host registry" in s or "DETACHED" in s or "detached" in s:
            for key in re.findall(r"cortex\.[a-z0-9_.]+@[0-9.]+", s):
                if key in ORGANS:
                    return {"kind": "CAPABILITY_ATTACH", "body": {"capability_id": ORGANS[key]}, "source": "parser:withheld"}
            for cid in re.findall(r"cognition\.[a-z0-9_.]+", s):
                return {"kind": "CAPABILITY_ATTACH", "body": {"capability_id": cid.rstrip(".")}, "source": "parser:detached"}
    missing = " ".join(str(x) for x in (last.get("missing_information") or []))
    named = [k for k in PART_KEYS if re.search(rf"\b{k}\b", missing) and k in item["removed"]]
    if named:                                                          # (2) inputs the receipt names
        request = _request(item)
        for k in named:
            _put(request, k, item["removed"][k])
        return {"kind": "MISSION", "body": _with_request(spec, request, _mission_id(item, "-r1")), "source": "parser:inputs"}
    fits = ((last.get("derived_geometry") or {}).get("fits_by_inputs") or [])
    declared = _declared(item)
    derived = fits[0] if fits else ((last.get("proof_artifact") or {}).get("geometry") or {}).get("epistemic_class")
    if derived and declared and derived != declared:                   # (3) a declaration its inputs contradict
        request = _request(item)
        _declare(request, derived)
        return {"kind": "MISSION", "body": _with_request(spec, request, _mission_id(item, "-r1")), "source": "parser:declaration"}
    return None


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _put(request: dict, key: str, value) -> None:
    if "compile" in request:
        request["compile"]["data"][key] = copy.deepcopy(value)
    else:
        request["problem"]["payload"][key] = copy.deepcopy(value)


def _declared(item: dict) -> str | None:
    if item["wrap"] == "compile":
        return (item.get("geometry") or {}).get("geometry")
    return ((item.get("payload") or {}).get("declared") or {}).get("epistemic_class")


def _declare(request: dict, cls: str) -> None:
    if "compile" in request:
        request["compile"]["geometry"]["geometry"] = cls
    else:
        declared = request["problem"]["payload"].setdefault("declared", {})
        declared["epistemic_class"] = cls


POLICIES = {"standard": standard_founder, "parser": parser_founder, "none": lambda *a: None}


# ------------------------------------------------------------------ one item
def run_item(item: dict, policy: str) -> dict:
    from greg.body import Body
    from tests.greg_fixtures import Clock, drop, make_body, signed
    started = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="resolution-"))
    home, key, body_id, _ = make_body(tmp)
    for i, cid in enumerate(item["detach"]):
        drop(home, signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": cid}), name=f"a{i}-detach.json")
    mid = _mission_id(item)
    request = _request(item)
    spec = _spec(item, request, mid)
    drop(home, signed(key, body_id, "MISSION", spec), name="z-mission.json")
    clock = Clock()
    record = {"item_id": item["item_id"], "operator": item["operator"], "policy": policy, "mission_id": mid,
              "ticks": [], "harm": False}
    try:
        with Body(home, clock=clock) as body:
            body.boot()
            successor = None
            for phase in ("before", "after"):
                for t in range(TICKS):
                    tick = body.tick()
                    states = {x.get("mission_id"): x.get("state") for x in tick.get("missions", [])}
                    record["ticks"].append({"phase": phase, "tick": t, "states": states,
                                            "genesis": _genesis(body, mid)})
                    for m in (mid, successor):
                        if m and _harm(item, body, states.get(m) == "ACHIEVED"):
                            record["harm"] = True
                    clock.advance(ADVANCE_S)
                if phase == "before":
                    record["achieved_before_action"] = any(
                        tk["states"].get(mid) == "ACHIEVED" for tk in record["ticks"])
                    record["asks_before"] = _asks(body, mid)
                    action = POLICIES[policy](body, item, mid, spec)
                    record["action"] = None if action is None else {k: action[k] for k in ("kind", "source")}
                    if action is not None:
                        if action["kind"] == "MISSION":
                            successor = action["body"]["mission_id"]
                            record["successor"] = successor
                            record["successor_spec_digest"] = _digest(action["body"])
                        drop(home, signed(key, body_id, action["kind"], action["body"]), name="zz-founder.json")
            final = {m: body.engine.book.missions.get(m) for m in (mid, successor) if m}
            record["closed"] = any(
                getattr(final.get(m), "status", None) == "ACHIEVED" and "VERIFIED" in _appraised(body, m)
                for m in final) and record["action"] is not None
            record["achieved_after"] = {m: getattr(v, "status", None) for m, v in final.items()}
            record["appraised"] = {m: _appraised(body, m) for m in final}
            record["genesis_first_tick"] = next((i for i, tk in enumerate(record["ticks"]) if tk["genesis"]), None)
            record["asks_after"] = _asks(body, mid)
    except Exception as exc:  # noqa: BLE001 - a crashed run is recorded, never retried
        record["error"] = f"{type(exc).__name__}: {exc}"[:400]
    record["seconds"] = round(time.time() - started, 2)
    return record


def _digest(obj) -> str:
    import hashlib
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _worker(args):
    item, policy = args
    return run_item(item, policy)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", required=True)
    ap.add_argument("--suite", type=Path, required=True)
    ap.add_argument("--policy", choices=sorted(POLICIES), required=True)
    ap.add_argument("--ablate", choices=("consumer", "producer"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--only", help="comma-separated item ids")
    args = ap.parse_args(argv)
    suite = json.loads(args.suite.read_text())
    items = suite["items"]
    if args.only:
        wanted = set(args.only.split(","))
        items = [i for i in items if i["item_id"] in wanted]
    tree = str(Path(args.tree).resolve())
    with ProcessPoolExecutor(max_workers=args.jobs, initializer=_enter, initargs=(tree, args.ablate)) as pool:
        rows = list(pool.map(_worker, [(i, args.policy) for i in items]))
    import subprocess
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tree, capture_output=True, text=True).stdout.strip()
    args.out.write_text(json.dumps({"schema": "greg-resolution-run/1", "tree_commit": commit, "policy": args.policy,
                                    "ablate": args.ablate, "suite_digest": suite.get("digest"), "rows": rows},
                                   indent=1, sort_keys=True) + "\n")
    print(json.dumps({"rows": len(rows), "errors": sum("error" in r for r in rows),
                      "closed": sum(bool(r.get("closed")) for r in rows), "harm": sum(r["harm"] for r in rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
