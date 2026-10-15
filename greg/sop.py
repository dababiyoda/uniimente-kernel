"""SOP compounding: stop paying intelligence to rediscover the same procedure (path node N4).

1. **Observe.** The systems worker watches verified closures. When at least three missions
   closed with the same ordered capabilities *and* the same signed shape, it proposes a
   Standard Operating Procedure. Nothing self-promotes.
2. **Generalize.** The proposal carries a workflow: the least general generalization
   (anti-unification, Plotkin 1970) of the founder-signed specs of those closures. What was
   identical in every run is fixed; what differed becomes a named slot, but only in parameter
   positions (sensor and strategy inputs, targets, predicate values, descriptions, the founder's
   words). Checks, predicate operators, capabilities, preconditions, strategy order and the light
   cone must be identical in every run, or the runs are not one procedure. A differing string is
   re-expressed through slots already found (and their basenames) when that reproduces every run
   exactly, so a run asks only for the inputs that genuinely varied. Every run is rebuilt from the
   workflow before it is proposed; a workflow that cannot reproduce its own evidence is refused.
3. **Ratify.** A founder-signed SOP_RATIFY registers the procedure. It may name ``pre_approve``:
   steps Alfonso approved in every one of those runs, internal at most and free. Nothing else.
4. **Run.** ``instantiate`` fills the slots and returns a complete mission with zero model calls.
   Alfonso still signs every run. Each pre-approved step is named in that signed run
   (``pre_approved_steps``: its own capability, target and class, free), so it no longer stops for
   approval: the approval moves to the signature he gives this run; it is not inherited. The cone is
   not widened, so every other step still asks exactly as it did in the verified runs.
5. **Measure.** ``trend`` reports, per procedure, founder interventions, GREG's own model calls and
   model cost per verified outcome for the runs before ratification and the runs from the SOP.
   Quality held means every finished SOP run was appraised VERIFIED and none was rejected.

Compounding is measured, not asserted; its absence is reported as plainly as its presence.
"""
from __future__ import annotations

from collections import defaultdict
import copy
from datetime import datetime, timedelta, timezone
import json
import math
import re

from greg.founder import CLOCK_SKEW            # the signer's clock may run this far ahead of the body's
from greg.journal import Journal, iso
from provenance.ledger import sha256_json

MIN_OCCURRENCES = 3
MIN_SOP_RUNS = 3
ORIGIN = "sop:"
REQUIRED_CHECKS = ("chain_intact", "founder_signature_verified", "checks_rederived_from_receipts",
                   "world_reobserved", "exactly_once", "deliveries_bound_to_evidence",
                   "approval_boundaries_honored")
CLASS_ORDER = ("read_only", "internal_write", "external_contact")
PRE_APPROVABLE = ("read_only", "internal_write")     # contact with the world and spend always ask
MASKED = (("mission_id",), ("light_cone", "horizon"), ("provenance",), ("venture",))
ROLE_ORDER = {"input": 0, "value": 1, "param": 2, "target": 3, "text": 4}
BUILTIN_NAMES = ("mission_id", "mission_dir")
MIN_SUBSTITUTION = 2
TOKEN = re.compile(r"\{\{|\}\}|\{([a-z][a-z0-9_]*)(\|basename)?\}|[{}]")
# This module's own workflow markers ({"$slot"}, {"$format"}) and shape placeholder ({"$type"}). Only these
# are reserved in a signed spec. Other "$" keys belong to the founder-signed structure, such as a typed
# handoff {"$from_action": ...} (greg/pipeline.py) or a composition {"$param": ...}: they and everything under
# them must be identical in every run of one procedure and never become a slot.
SOP_MARKERS = ("$slot", "$format", "$type")


class SopError(ValueError):
    """The runs are not one procedure, or a run does not fit its ratified workflow."""


def verified_appraisals(journal: Journal) -> dict[str, str]:
    """Latest appraisal wins; an achievement alone does not establish an outcome.

    This is the body's separate-process appraisal, not an external trust root.
    Its event ID records which local evidence supported a proposal.
    """
    latest = {}
    for event in journal.replay("mission.appraised"):
        latest[event.payload["mission_id"]] = event
    return {mid: event.event_id for mid, event in latest.items()
            if event.payload.get("verdict") == "VERIFIED"
            and all(event.payload.get("checks", {}).get(check) is True for check in REQUIRED_CHECKS)}


def closed_procedures(journal: Journal) -> dict[str, list]:
    """mission_id -> ordered capabilities of DONE actions for locally verified closures."""
    achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
    achieved.intersection_update(verified_appraisals(journal))
    steps = defaultdict(list)
    for event in journal.replay("mission.action"):
        data = event.payload
        if data["mission_id"] in achieved and data["status"] == "DONE":
            steps[data["mission_id"]].append(data["capability"])
    return dict(steps)


# -- generalization ---------------------------------------------------------------------------

def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _dotted(path) -> str:
    return ".".join(str(p) for p in path)


def _masked(path) -> bool:
    return any(path[:len(m)] == m for m in MASKED)


def _leaves(value, path=()):
    """(path, scalar) pairs in document order; empty containers are structure, kept as leaves."""
    if isinstance(value, dict):
        if not value:
            yield path, {}
        for key, item in value.items():
            if key in SOP_MARKERS:
                raise SopError(f"{_dotted(path + (key,))}: {key} is reserved for SOP workflows")
            yield from _leaves(item, path + (key,))
    elif isinstance(value, list):
        if not value:
            yield path, []
        for index, item in enumerate(value):
            yield from _leaves(item, path + (index,))
    else:
        yield path, value


def _role(path) -> str | None:
    """The parameter role of a leaf, or None when it must be identical in every run of a procedure."""
    if any(isinstance(p, str) and p.startswith("$") for p in path):
        return None                          # inside signed structure such as a typed handoff: never a slot
    if path in (("founder_expression",), ("intended_effect",)):
        return "text"
    if len(path) >= 3 and isinstance(path[1], int):
        tail = path[2:]
        if path[0] == "success_checks":
            if tail[:2] == ("sensor", "params") and len(tail) > 2:
                return "input"
            if tail[:2] == ("predicate", "value"):
                return "value"
            if tail == ("sensor", "target"):
                return "target"
            if tail == ("description",):
                return "text"
        if path[0] == "strategies":
            if tail[0] == "params" and len(tail) > 1:
                return "param"
            if tail == ("target",):
                return "target"
            if tail in (("rationale",), ("expected_outcome",)):
                return "text"
    return None


def shape(spec: dict) -> str:
    """Digest of everything that must be identical across runs of one procedure."""
    return sha256_json([[list(path), {"$type": type(value).__name__} if _role(path) else value]
                        for path, value in _leaves(spec) if not _masked(path)])


def _slot_type(value) -> str:
    return {bool: "boolean", int: "integer", float: "number", str: "string"}[type(value)]


def _slot_name(path, spec: dict, taken) -> str:
    raw = None
    if _role(path) == "value":
        raw = spec["success_checks"][path[1]]["predicate"].get("field")
    raw = raw or next((p for p in reversed(path) if isinstance(p, str)), "value")
    base = re.sub(r"[^a-z0-9_]+", "_", str(raw).lower()).strip("_") or "value"
    if not base[0].isalpha():
        base = "v_" + base
    name, n = base, 2
    while name in taken or name in BUILTIN_NAMES:
        name, n = f"{base}_{n}", n + 1
    return name


def _escape(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")


def _substitute(value: str, subs: list) -> str:
    out, i = [], 0
    while i < len(value):
        hit = next(((text, hole) for text, hole in subs if value.startswith(text, i)), None)
        if hit:
            out.append(hit[1])
            i += len(hit[0])
        else:
            out.append(_escape(value[i]))
            i += 1
    return "".join(out)


def _basename(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


def _derive(values: list, env: list) -> str | None:
    """One format string over known slots that reproduces every run exactly, or None."""
    rendered = []
    for value, names in zip(values, env):
        subs = []
        for name, known in names.items():
            if isinstance(known, bool) or not isinstance(known, (str, int, float)):
                continue
            if len(str(known)) >= MIN_SUBSTITUTION:
                subs.append((str(known), "{" + name + "}"))
            if isinstance(known, str) and "/" in known and len(_basename(known)) >= MIN_SUBSTITUTION:
                subs.append((_basename(known), "{" + name + "|basename}"))
        subs.sort(key=lambda s: (-len(s[0]), s[1]))
        rendered.append(_substitute(value, subs))
        if rendered[-1] != rendered[0]:
            return None
    template = rendered[0]
    return template if any(m.group(1) for m in TOKEN.finditer(template)) else None


def render(template: str, env: dict) -> str:
    out, last = [], 0
    for match in TOKEN.finditer(template):
        out.append(template[last:match.start()])
        token = match.group(0)
        if token in ("{{", "}}"):
            out.append(token[0])
        elif match.group(1) is None or match.group(1) not in env:
            raise SopError(f"workflow text names an unknown slot: {token}")
        else:
            value = env[match.group(1)]
            out.append(_basename(value) if match.group(2) else str(value))
        last = match.end()
    return "".join(out) + template[last:]


def _fill(node, env: dict):
    if isinstance(node, dict):
        if set(node) == {"$slot"}:
            return env[node["$slot"]]
        if set(node) == {"$format"}:
            return render(node["$format"], env)
        return {k: _fill(v, env) for k, v in node.items()}
    if isinstance(node, list):
        return [_fill(v, env) for v in node]
    return node


def _set(tree, path, value):
    for part in path[:-1]:
        tree = tree[part]
    tree[path[-1]] = value


def _strip(spec: dict) -> dict:
    out = copy.deepcopy({k: v for k, v in spec.items() if k not in ("mission_id", "provenance", "venture")})
    out.get("light_cone", {}).pop("horizon", None)
    return out


def _env(mission_id: str, slots: dict) -> dict:
    return {"mission_id": mission_id, "mission_dir": mission_id.replace(":", "_"), **slots}


def _seeds(specs: list[dict]) -> dict:
    """Template inputs every run recorded and that differed between runs: the first candidates for slots.

    A template records its normalized inputs in the signed provenance (attribution, never
    authority). Seeding derivation with them lets a procedure ask only for what a person chose
    (a buyer, a price), instead of every text that repeats it. The workflow must still rebuild
    every run exactly, so a misleading record cannot change what a run does."""
    records = [(s.get("provenance") or {}).get("inputs") for s in specs]
    if not all(isinstance(r, dict) for r in records):
        return {}
    names = set.intersection(*(set(r) for r in records))
    seeds = {}
    for name in sorted(names):
        values = [r[name] for r in records]
        if re.fullmatch(r"[a-z][a-z0-9_]*", name) and name not in BUILTIN_NAMES \
                and all(isinstance(v, (str, int, float)) and not isinstance(v, bool) for v in values) \
                and all(type(v) is type(values[0]) for v in values) \
                and any(not _same(v, values[0]) for v in values) and all(len(str(v)) >= MIN_SUBSTITUTION for v in values):
            seeds[name] = values
    return seeds


def generalize(specs: list[dict]) -> dict:
    """The least general workflow that reproduces every signed spec exactly, or SopError."""
    if len(specs) < 2:
        raise SopError("a procedure needs at least two runs to generalize")
    tables = [dict((p, v) for p, v in _leaves(s) if not _masked(p)) for s in specs]
    paths = list(tables[0])
    if any(list(t) != paths for t in tables):
        raise SopError("the runs differ in structure")
    varying = [p for p in paths if any(not _same(t[p], tables[0][p]) for t in tables)]
    authority = [_dotted(p) for p in varying if _role(p) is None]
    if authority:
        raise SopError("these differ between runs but are not parameters: " + ", ".join(authority[:5]))
    seeds = _seeds(specs)
    env = [_env(s["mission_id"], {name: values[i] for name, values in seeds.items()}) for i, s in enumerate(specs)]
    slots, holes = {}, {}
    for path in sorted(varying, key=lambda p: (ROLE_ORDER[_role(p)], paths.index(p))):
        values = [t[path] for t in tables]
        template = _derive(values, env) if all(isinstance(v, str) for v in values) else None
        if template is not None:
            holes[path] = {"$format": template}
            continue
        if not isinstance(values[0], (str, int, float, bool)) or any(type(v) is not type(values[0]) for v in values):
            raise SopError(f"{_dotted(path)} varies in type or is not a single value")
        if isinstance(values[0], str) and not all(values):
            raise SopError(f"{_dotted(path)} is empty in a run")
        name = _slot_name(path, specs[0], {**seeds, **slots})
        slots[name] = {"type": _slot_type(values[0]), "at": _dotted(path), "role": _role(path), "examples": values}
        for names, value in zip(env, values):
            names[name] = value
        holes[path] = {"$slot": name}
    used = {m.group(1) for hole in holes.values() if "$format" in hole for m in TOKEN.finditer(hole["$format"])
            if m.group(1)}
    slots = {**{name: {"type": _slot_type(values[0]), "at": "provenance.inputs." + name, "role": "input",
                       "examples": values} for name, values in seeds.items() if name in used}, **slots}
    skeleton = _strip(specs[0])
    for path, hole in holes.items():
        _set(skeleton, path, hole)
    for spec, names in zip(specs, env):     # the workflow must reproduce its own evidence
        if not _same(_fill(skeleton, names), _strip(spec)):
            raise SopError(f"the generalized workflow does not reproduce {spec['mission_id']}")
    return {"skeleton": skeleton, "slots": slots}


# -- observation and proposal -----------------------------------------------------------------

def _registered(journal: Journal) -> dict:
    return {e.payload["mission_id"]: e for e in journal.replay("mission.registered")}


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _horizon_days(events: list) -> float:
    """The longest mandate any of the runs was signed with, rounded up to the hour."""
    seconds = max((_instant(e.payload["spec"]["light_cone"]["horizon"]) - _instant(e.occurred_at)).total_seconds()
                  for e in events)
    return max(1, math.ceil(seconds / 3600)) / 24


def _approvals(journal: Journal, missions) -> dict:
    """action_id -> {missions it was approved in, what was approved} for founder APPROVAL answers."""
    answers = {e.payload["request_id"]: e.payload["answer"] for e in journal.replay("decision.answered")}
    out = {}
    for event in journal.replay("decision.requested"):
        r = event.payload
        if r["mission_id"] in missions and r["kind"] == "APPROVAL" and r.get("action_id") \
                and answers.get(r["request_id"]) == "approve":
            entry = out.setdefault(r["action_id"], {"missions": set(), "requested": []})
            entry["missions"].add(r["mission_id"])
            entry["requested"].append(r.get("authority_requested") or {})
    return out


def _pre_approvable(journal: Journal, missions: list, skeleton: dict) -> list[dict]:
    steps = {s["action_id"]: s for s in skeleton["strategies"]}
    out = []
    for aid, entry in sorted(_approvals(journal, set(missions)).items()):
        classes = {r.get("consequence_class") for r in entry["requested"]}
        capabilities = {r.get("capability") for r in entry["requested"]}
        if entry["missions"] != set(missions) or len(classes) != 1 or len(capabilities) != 1:
            continue
        cls, capability = classes.pop(), capabilities.pop()
        costs = {float(r.get("cost_usd") or 0) for r in entry["requested"]}
        step = steps.get(aid)
        if cls in PRE_APPROVABLE and costs == {0.0} and step and step.get("capability") == capability \
                and float(step.get("cost_usd", 0) or 0) == 0:
            out.append({"action_id": aid, "capability": capability, "consequence_class": cls,
                        "approved_in": len(entry["missions"])})
    return out


def _groups(journal: Journal) -> dict:
    registered = _registered(journal)
    groups = defaultdict(list)
    for mission_id, sequence in closed_procedures(journal).items():
        event = registered.get(mission_id)
        if event is None or not sequence:
            continue
        if str(event.payload["spec"].get("provenance", {}).get("origin", "")).startswith(ORIGIN):
            continue            # runs of a ratified SOP are its measurements, not new evidence for proposals
        try:
            signed_shape = shape(event.payload["spec"])
        except SopError:
            continue            # a spec this module cannot represent is no procedure's run; never fatal to a tick
        groups[(tuple(sequence), signed_shape)].append(mission_id)
    return groups


def procedure_id(steps, signed_shape: str) -> str:
    return "sop-" + sha256_json({"steps": list(steps), "shape": signed_shape})[7:23]


def propose(journal: Journal) -> list[dict]:
    appraisals = verified_appraisals(journal)
    registered = _registered(journal)
    existing = {e.payload["procedure_id"] for e in journal.replay("sop.proposed")}
    proposals = []
    for (sequence, signed_shape), missions in _groups(journal).items():
        pid = procedure_id(sequence, signed_shape)
        if len(missions) < MIN_OCCURRENCES or pid in existing:
            continue
        missions = sorted(missions)
        record = {"procedure_id": pid, "steps": list(sequence), "occurrences": len(missions),
                  "missions": missions, "actions_per_outcome": len(sequence),
                  "appraisal_events": {mid: appraisals[mid] for mid in missions}, "shape": signed_shape,
                  "evidence_level": "local separate-process appraisal; external outcome unproven",
                  "state": "PROPOSED", "promotion": "requires founder SOP_RATIFY"}
        try:
            workflow = generalize([registered[mid].payload["spec"] for mid in missions])
        except SopError as exc:
            record["workflow_unavailable"] = str(exc)[:300]
        else:
            workflow["horizon_days"] = _horizon_days([registered[mid] for mid in missions])
            ventures = {registered[mid].payload["spec"].get("venture") for mid in missions}
            if len(ventures) == 1 and None not in ventures:
                workflow["venture"] = ventures.pop()
            record["workflow"] = workflow
            record["pre_approvable"] = _pre_approvable(journal, missions, workflow["skeleton"])
        journal.record("sop.proposed", record, key=pid)
        proposals.append(record)
    return proposals


def ratify(journal: Journal, body: dict, command_digest: str) -> dict:
    pid = body.get("procedure_id")
    proposed = [e for e in journal.replay("sop.proposed") if e.payload["procedure_id"] == pid]
    if not proposed:
        raise ValueError("unknown SOP proposal")
    proposal = proposed[0].payload
    current = closed_procedures(journal)
    if any(current.get(mid) != proposal["steps"] for mid in proposal["missions"]):
        raise ValueError("SOP proposal no longer locally appraised as verified; inspect its evidence")
    pre = body.get("pre_approve", [])
    if not isinstance(pre, list) or not all(isinstance(a, str) for a in pre) or len(set(pre)) != len(pre):
        raise ValueError("pre_approve is a list of distinct step ids")
    offered = {s["action_id"]: s for s in proposal.get("pre_approvable", [])}
    beyond = sorted(set(pre) - set(offered))
    if beyond:
        raise ValueError(f"only steps you approved in every verified run, internal and free, can be pre-approved; "
                         f"not {beyond}")
    record = {"procedure_id": pid, "steps": proposal["steps"], "state": "RATIFIED",
              "command_digest": command_digest, "authority_inherited": False,
              "proposal_event": proposed[0].event_id}
    if "workflow" in proposal:
        record["workflow"] = proposal["workflow"]
        record["pre_approved_steps"] = [offered[a] for a in sorted(pre)]
    journal.record("sop.ratified", record, key=pid)
    return record


def ratified(journal: Journal) -> dict[str, dict]:
    """procedure_id -> {"record", "event_id"} of its ratification."""
    return {e.payload["procedure_id"]: {"record": e.payload, "event_id": e.event_id}
            for e in journal.replay("sop.ratified")}


# -- running a ratified procedure ---------------------------------------------------------------

def _check_slots(declared: dict, slots: dict):
    missing, unknown = sorted(set(declared) - set(slots)), sorted(set(slots) - set(declared))
    if missing or unknown:
        raise SopError(f"this procedure takes exactly {sorted(declared)}; missing {missing}, unknown {unknown}")
    for name, value in slots.items():
        want = declared[name]["type"]
        ok = {"string": isinstance(value, str) and 0 < len(value) <= 2000,
              "integer": isinstance(value, int) and not isinstance(value, bool),
              "number": isinstance(value, (int, float)) and not isinstance(value, bool),
              "boolean": isinstance(value, bool)}[want]
        if not ok:
            raise SopError(f"slot {name} must be a {want}" + (" of 1-2000 characters" if want == "string" else ""))


def instantiate(record: dict, slots: dict, *, now: datetime | None = None, horizon_days: float | None = None,
                mission_id: str | None = None, venture: str | None = None) -> dict:
    """A complete mission for one run of a ratified procedure: zero model calls; Alfonso signs it."""
    from greg.missions import validate_mission
    workflow = record.get("workflow")
    if not workflow:
        raise SopError("this ratification carries no workflow (it predates workflows, or the runs could not be "
                       "generalized); it can only be measured")
    _check_slots(workflow["slots"], slots)
    days = workflow["horizon_days"] if horizon_days is None else float(horizon_days)
    if not 0 < days <= workflow["horizon_days"]:
        raise SopError(f"a run's mandate may last at most {workflow['horizon_days']} days, as the verified runs did")
    now = now or datetime.now(timezone.utc)
    # Each run is its own mission, even with the same inputs (a daily procedure), so the id binds the time.
    mission_id = mission_id or f"m:{record['procedure_id']}-{sha256_json({'slots': slots, 'at': iso(now)})[7:17]}"
    spec = {"mission_id": mission_id, **_fill(workflow["skeleton"], _env(mission_id, slots))}
    cone = spec["light_cone"]
    cone["horizon"] = iso(now + timedelta(days=days))
    strategies = {s["action_id"]: s for s in spec["strategies"]}
    # Each pre-approved step is carried as itself, never by widening the cone. Widening the cone's
    # capabilities and its one ceiling admitted every sibling strategy with the same capability and
    # class, so a step Alfonso did not pre-approve ran without the approval it asked for in every
    # verified run (review of 2026-10-14). The engine admits exactly these strategies past the cone.
    pre = []
    for step in record.get("pre_approved_steps", []):
        strategy = strategies[step["action_id"]]
        if strategy.get("capability") != step["capability"] or float(strategy.get("cost_usd", 0) or 0) != 0:
            raise SopError(f"pre-approved step {step['action_id']} no longer matches its ratified capability")
        pre.append({"action_id": step["action_id"], "capability": step["capability"], "target": strategy["target"],
                    "consequence_class": step["consequence_class"], "cost_usd": 0})
    spec.pop("pre_approved_steps", None)            # only this ratification's steps, never a taught run's
    if pre:
        spec["pre_approved_steps"] = pre
    if venture or workflow.get("venture"):          # a procedure taught in one venture may run in another
        spec["venture"] = venture or workflow["venture"]
    spec["provenance"] = {"origin": ORIGIN + record["procedure_id"], "planner": "greg.sop/1",
                          "procedure_id": record["procedure_id"], "ratification": record["command_digest"],
                          "slots": slots, "model_calls": 0, "model_cost_usd": 0.0}
    return validate_mission(spec)


def instantiates(record: dict, spec: dict, *, registered_at: str | None = None) -> dict | None:
    """The slot values when ``spec`` is exactly one run of the ratified workflow; otherwise None.

    With ``registered_at``, a run whose mandate outlasts the verified runs' is not an instance."""
    provenance = spec.get("provenance") or {}
    workflow = record.get("workflow")
    if not workflow or provenance.get("origin") != ORIGIN + record["procedure_id"]:
        return None
    if registered_at is not None and (_instant(spec["light_cone"]["horizon"]) - _instant(registered_at)
                                      > timedelta(days=workflow["horizon_days"]) + CLOCK_SKEW):
        return None
    slots = provenance.get("slots")
    if not isinstance(slots, dict):
        return None
    try:
        expected = instantiate(record, slots, now=_instant(spec["light_cone"]["horizon"]) - timedelta(
            days=workflow["horizon_days"]), mission_id=spec["mission_id"], venture=spec.get("venture"))
    except (SopError, ValueError, KeyError):
        return None
    expected["light_cone"]["horizon"] = spec["light_cone"]["horizon"]
    return slots if _same(_strip(expected), _strip(spec)) and \
        provenance.get("ratification") == record["command_digest"] else None


# -- measurement --------------------------------------------------------------------------------

def _mission_costs(journal: Journal) -> dict:
    """mission_id -> founder interventions (by kind), GREG's own model calls and model cost."""
    out = defaultdict(lambda: {"interventions": defaultdict(int), "model_calls": 0, "model_cost_usd": 0.0,
                               "cost_known": True})
    for event in journal.replay("decision.requested"):
        out[event.payload["mission_id"]]["interventions"][event.payload["kind"]] += 1
    for kind, label in (("mission.lifecycle", "LIFECYCLE"), ("mission.strategy_excluded", "STRATEGY_EXCLUDED")):
        for event in journal.replay(kind):
            out[event.payload["mission_id"]]["interventions"][label] += 1
    for mid, event in _registered(journal).items():
        provenance = event.payload["spec"].get("provenance") or {}
        if str(provenance.get("origin", "")).startswith("model:"):
            out[mid]["model_calls"] += int(provenance.get("model_calls", provenance.get("rounds", 1)))
            if provenance.get("model_cost_usd") is None:
                out[mid]["cost_known"] = False
            out[mid]["model_cost_usd"] += float(provenance.get("model_cost_usd") or 0.0)
    deficits = {e.payload["deficit_id"]: e.payload["mission_id"] for e in journal.replay("deficit.opened")}
    for event in journal.replay("genesis.built"):
        mid = deficits.get(event.payload["deficit_id"])
        if mid is None:
            continue
        if event.payload.get("builder") != "static":        # StaticBuilder: a human-supplied implementation
            out[mid]["model_calls"] += 1
        cost = event.payload.get("cost_usd")
        if cost is None:
            out[mid]["cost_known"] = False
        out[mid]["model_cost_usd"] += float(cost or 0.0)
    return out


def _summary(rows: list) -> dict:
    n = len(rows)
    if not n:
        return {"verified_outcomes": 0, "interventions_per_outcome": None, "model_calls_per_outcome": None,
                "model_cost_usd_per_outcome": None, "cost_known": True}
    return {"verified_outcomes": n,
            "interventions_per_outcome": round(sum(r["interventions"] for r in rows) / n, 4),
            "model_calls_per_outcome": round(sum(r["model_calls"] for r in rows) / n, 4),
            "model_cost_usd_per_outcome": round(sum(r["model_cost_usd"] for r in rows) / n, 6),
            "cost_known": all(r["cost_known"] for r in rows)}


def trend(journal: Journal) -> dict:
    """Per procedure: the runs that taught it, the runs from it, and whether compounding is real."""
    seq = {r.payload.get("event_id"): r.seq for r in journal.ledger.by_type("event")}
    registered = _registered(journal)
    verified = verified_appraisals(journal)
    achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
    latest = {}
    for event in journal.replay("mission.appraised"):
        latest[event.payload["mission_id"]] = event.payload.get("verdict")
    owners = {e.event_id: e.payload.get("mission_id") for e in journal.replay()}
    rejected = {owners.get(e.payload["target_event_id"]) for e in journal.replay("critique.recorded")
                if e.payload["verdict"] == "reject"}
    terminal = {e.payload["mission_id"] for e in journal.replay("mission.lifecycle")
                if e.payload["state"] in ("ABANDONED", "SUPERSEDED")}
    costs = _mission_costs(journal)
    accepted = ratified(journal)

    closed_at = {e.payload["mission_id"]: e.occurred_at for e in journal.replay("mission.achieved")}

    def row(mid):
        c = costs[mid]
        hours = None
        if mid in closed_at and mid in registered:   # to 0.01 h: nothing finer is a real difference in pace
            hours = round(max(0.0, (_instant(closed_at[mid]) - _instant(registered[mid].occurred_at))
                              .total_seconds() / 3600), 2)
        return {"mission_id": mid, "interventions": sum(c["interventions"].values()),
                "by_kind": dict(sorted(c["interventions"].items())), "model_calls": c["model_calls"],
                "model_cost_usd": round(c["model_cost_usd"], 6), "cost_known": c["cost_known"],
                "hours_to_close": hours}

    report = []
    for event in journal.replay("sop.proposed"):
        proposal = event.payload
        pid = proposal["procedure_id"]
        baseline = [row(mid) for mid in proposal["missions"]]
        entry = {"procedure_id": pid, "steps": proposal["steps"], "state": "PROPOSED",
                 "baseline": {"missions": baseline, **_summary(baseline)}}
        rat = accepted.get(pid)
        if rat is None:
            entry["compounding"] = False
            entry["why_not"] = ["not ratified"]
            report.append(entry)
            continue
        record, rat_seq = rat["record"], seq.get(rat["event_id"], 1 << 60)
        entry.update(state="RATIFIED", pre_approved=[s["action_id"] for s in record.get("pre_approved_steps", [])],
                     runnable=bool(record.get("workflow")))
        runs, claimed, failures = [], [], []
        for mid, reg in sorted(registered.items(), key=lambda kv: seq.get(kv[1].event_id, 0)):
            origin = (reg.payload["spec"].get("provenance") or {}).get("origin")
            if origin != ORIGIN + pid:
                continue
            if seq.get(reg.event_id, 0) < rat_seq or instantiates(record, reg.payload["spec"],
                                                                  registered_at=reg.occurred_at) is None:
                claimed.append(mid)
                continue
            if mid in rejected or latest.get(mid) not in (None, "VERIFIED") or mid in terminal \
                    or (mid in latest and mid not in verified):
                failures.append({"mission_id": mid, "appraisal": latest.get(mid),
                                 "rejected_by_founder": mid in rejected, "ended": mid in terminal})
            elif mid in achieved and mid in verified:
                runs.append(row(mid))
        after = _summary(runs)
        before = entry["baseline"]
        entry["sop_runs"] = {"missions": runs, **after, "quality_failures": failures,
                             "claimed_but_not_instantiating": claimed}
        why = []
        if not record.get("workflow"):
            why.append("no workflow to run: " + proposal.get("workflow_unavailable", "ratified before workflows existed"))
        if after["verified_outcomes"] < MIN_SOP_RUNS:
            why.append(f"{after['verified_outcomes']} of {MIN_SOP_RUNS} verified runs from the SOP")
        if failures:
            why.append("quality not held: a run from the SOP failed appraisal, was rejected or ended")
        if not (before["cost_known"] and after["cost_known"]):
            why.append("model cost unknown for some run")
        if after["verified_outcomes"]:
            if not after["interventions_per_outcome"] < before["interventions_per_outcome"]:
                why.append("founder interventions per outcome did not fall")
            if after["model_cost_usd_per_outcome"] > before["model_cost_usd_per_outcome"] or (
                    before["model_cost_usd_per_outcome"] > 0
                    and not after["model_cost_usd_per_outcome"] < before["model_cost_usd_per_outcome"]):
                why.append("model cost per outcome did not fall")
            if after["model_calls_per_outcome"] > before["model_calls_per_outcome"]:
                why.append("model calls per outcome rose")
        entry["compounding"] = not why
        if why:
            entry["why_not"] = why
        report.append(entry)
    return {"procedures": report, "compounding": [p["procedure_id"] for p in report if p["compounding"]],
            "measures": "founder interventions = decision requests, lifecycle commands and strategy exclusions on "
                        "the mission; model cost = GREG's own planning and capability-build model spend",
            "reality": "local separate-process appraisal and the founder's critiques; external outcomes unproven"}


def model_usage(journal: Journal) -> dict:
    """GREG's own model calls and spend, attributed to missions, plus every routed attempt the body kept.

    Attribution (planner provenance, capability builds) is what the per-procedure trend needs. The
    count of retained ``model.route`` attempts (the mechanism of draft #145) also sees failed attempts
    and calls tied to no mission; it is a lower bound, since a call made outside GREG leaves no record.
    """
    costs = _mission_costs(journal)
    attempts = sum(e.payload.get("outcome") in ("ok", "failed", "refused") for e in journal.replay("model.route"))
    return {"model_calls": sum(c["model_calls"] for c in costs.values()),
            "model_cost_usd": round(sum(c["model_cost_usd"] for c in costs.values()), 6),
            "cost_known": all(c["cost_known"] for c in costs.values()),
            "model_route_attempts_recorded": attempts,
            "coverage": "attributed: planner drafts and capability builds per mission; recorded attempts: every "
                        "routed call the body kept, a lower bound; a model used outside GREG is invisible here"}


def awaiting_ratification(journal: Journal) -> list[dict]:
    """Proposals Alfonso has not ratified, with what ratifying would let a run skip."""
    done = set(ratified(journal))
    return [{"procedure_id": p["procedure_id"], "occurrences": p["occurrences"], "steps": p["steps"],
             "slots": sorted(p.get("workflow", {}).get("slots", {})),
             "pre_approvable": [s["action_id"] for s in p.get("pre_approvable", [])],
             **({"workflow_unavailable": p["workflow_unavailable"]} if "workflow_unavailable" in p else {}),
             "how": f"greg sop show {p['procedure_id']}; greg sop ratify {p['procedure_id']} --key <founder key>"}
            for p in (e.payload for e in journal.replay("sop.proposed")) if p["procedure_id"] not in done]


def compounding_metrics(journal: Journal) -> dict:
    achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
    verified = achieved.intersection(verified_appraisals(journal))
    outcomes = len(verified)
    actions = sum(1 for e in journal.replay("mission.action") if e.payload["status"] == "DONE")
    decisions = len(journal.replay("decision.requested"))
    costs = _mission_costs(journal)
    calls = sum(costs[mid]["model_calls"] for mid in verified)
    return {"verified_outcomes": outcomes,
            "actions_per_outcome": (actions / outcomes) if outcomes else None,
            "founder_decisions_per_outcome": (decisions / outcomes) if outcomes else None,
            "model_calls_per_outcome": (calls / outcomes) if outcomes else None,
            "note": "null means no verified outcome yet; not zero cost and not infinite improvement"}
