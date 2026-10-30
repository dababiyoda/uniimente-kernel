"""Institutional self-knowledge on GREG's one mission path: survey, compose, deliver, appraise.

These four capabilities let one founder sentence ("understand where I am trying to go, find the
highest-value unfinished opportunity, compare ways to advance it, do useful work, verify it, and
tell me what is next") run as ONE signed mission whose steps hand typed outputs to each other:

  institution.survey    read-only. Reconstructs the current objective from GREG's own developmental
                        path (``greg/path.json`` through ``greg.path.position``: the one operationally
                        primary node and its gate) and the open opportunities from the founder's own
                        horizons and the Foundry completion contract. Anything only Alfonso can unblock
                        (a gate naming him, an execution-environment decision) is routed to the decision
                        queue and never offered as work. Each candidate is scored by a DECLARED model
                        (``SCORING_MODEL``): proximity to the primary node x readiness x breadth. The
                        scores are a stated prior over source fields, not measurements, and the model
                        travels with the result so the founder can see and change it.
  (selection)           not here: the mission binds ``survey.knapsack`` into ``cognition.dp_knapsack``,
                        GREG's exact 0/1 knapsack intelligence with its own verifier and LP bound.
  institution.compose   read-only. For every candidate, which machinery GREG already has (registered
                        capabilities and Foundry systems whose modules are the candidate's named
                        precursors, or the Foundry dependency closure of an open Foundry row) and what
                        is missing (a CapabilityDeficit), so the selected work starts from what exists.
  institution.dossier   internal write to the founder's delivery root. One private Markdown + JSON
                        deliverable: objective, decision queue, candidates, the exact selection against
                        the greedy baseline (the simpler method wins when it is as good), the
                        composition, a FROZEN acceptance contract for the next work order, uncertainty
                        and the next authorized step. Nothing is sent, published, spent or merged.
  institution.appraise  read-only sensor, independent of the steps above: re-reads the sources,
                        recomputes the survey, re-proves the selection's optimality with a different
                        algorithm (dynamic program over profit, not capacity), recomputes the greedy
                        baseline and refutes a dossier whose claims do not hold.

No output of any of these creates authority. The selection says what is worth doing; doing it is a
new signed mission or work order.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from greg.capabilities import CapabilityError, InvocationContext
from provenance.digests import compact_json_bytes, sha256_tagged as _sha

SCORING_MODEL = {
    "name": "declared-leverage-prior/1",
    "value": "proximity x readiness x breadth (integers; 1..27)",
    "proximity": {"primary node": 3, "next node": 2, "later node or Foundry obligation": 2, "other": 1},
    "readiness": {"INTEGRATION-TESTED or stronger": 3, "IMPLEMENTED / UNIT-TESTED / SANDBOXED": 2,
                  "PROPOSED / DOCUMENTED / ASPIRATIONAL / PARTIAL / unknown": 1},
    "breadth": "number of founder capabilities the item covers, capped at 3 (Foundry rows: acceptance criteria, capped at 3)",
    "effort": "readiness 3 -> 2 units, 2 -> 3 units, 1 -> 5 units; +1 when no precursor code is named",
    "status": "a stated prior over source fields, not a measurement; change it and the selection changes",
}
MAX_CANDIDATES = 60          # the exact DP genome is native to <= 60 items
FOUNDER_WORDS = ("alfonso", "founder", "authoriz", "privileged", "dedicated host", "execution-environment",
                 "execution environment", "purchase", "legal operator", "hardware")


def _canon(value) -> bytes:
    return compact_json_bytes(value, ensure_ascii=False)


def _inside(path: Path, roots) -> Path:
    resolved = Path(path).expanduser().resolve()
    for root in roots:
        try:
            resolved.relative_to(Path(root).resolve())
            return resolved
        except ValueError:
            continue
    raise CapabilityError(f"{path} is outside the founder's read roots")


def _kernel_root(params: dict, ctx: InvocationContext) -> Path:
    root = _inside(Path(params.get("kernel_root", "")), ctx.read_roots)
    for needed in ("greg/path.json", "foundry/completion.yaml"):
        if not (root / needed).is_file():
            raise CapabilityError(f"{root} is not a UNIIMENTE kernel checkout (no {needed})")
    return root


def _readiness(reality: str) -> int:
    r = (reality or "").upper()
    if "EXTERNALLY" in r or "INTEGRATION-TESTED" in r or "VERIFIED_IN_TESTED" in r:
        return 3
    if any(w in r for w in ("IMPLEMENTED", "UNIT-TESTED", "SANDBOXED")):
        return 2
    return 1


def _founder_gated(text: str) -> bool:
    t = (text or "").lower()
    return any(w in t for w in FOUNDER_WORDS)


def reconstruct(root: Path, journal=None) -> dict:
    """Objective, founder decisions and scored candidates from the kernel's own sources.

    ``journal`` (the body's ledger, when the mission provides it) lets ledger-measured nodes count as passed;
    without it, only repository-attested nodes can pass, exactly as ``greg path`` reports.
    """
    import yaml
    from greg import path as gpath
    path_bytes = (root / "greg/path.json").read_bytes()
    contract_bytes = (root / "foundry/completion.yaml").read_bytes()
    data = json.loads(path_bytes)
    contract = yaml.safe_load(contract_bytes)
    position = gpath.position(journal, data)
    nodes = {n["id"]: n for n in data["nodes"]}
    if position.get("active") is None:
        raise CapabilityError("every developmental node reports passed; there is no primary objective to reconstruct")
    primary_id = position["active"]["id"]
    nxt = (position.get("next") or {}).get("id")
    node = nodes[primary_id]
    objective = {"node": primary_id, "title": node["title"], "outcome": node.get("outcome", ""),
                 "gate": node.get("gate", ""), "founder_only_gate": _founder_gated(node.get("gate", "")),
                 "exit_evidence": node.get("exit_evidence", []), "destination": data.get("destination", ""),
                 "achieved": position.get("achieved", []), "measurement": position["active"].get("measurement")}
    decisions, candidates = [], []
    if objective["founder_only_gate"]:
        decisions.append({"source": f"greg/path.json#{primary_id}", "decision": node.get("gate", ""),
                          "why_founder": "the primary node's gate names an act only Alfonso can perform"})
    for h in data.get("horizons", []):
        if h.get("feasibility") != "CURRENTLY_BUILDABLE":
            continue
        proximity = 3 if h.get("node") == primary_id else 2 if h.get("node") == nxt else 1
        readiness = _readiness(h.get("current_reality", ""))
        breadth = max(1, min(3, len(h.get("covers", []))))
        precursors = h.get("nearest_precursor") or []
        candidates.append({"id": f"horizon:{h['id']}", "kind": "horizon", "title": h.get("intended_effect", h["id"]),
                           "node": h.get("node"), "reality": h.get("current_reality", "")[:240],
                           "precursors": precursors, "value": proximity * readiness * breadth,
                           "effort": {3: 2, 2: 3, 1: 5}[readiness] + (0 if precursors else 1),
                           "score_parts": {"proximity": proximity, "readiness": readiness, "breadth": breadth},
                           "source": f"greg/path.json#horizons/{h['id']}"})
    for sid, row in sorted(contract.items()):
        if row.get("state") == "COMPLETE":
            continue
        gap = row.get("gap", "")
        if _founder_gated(gap) or sid in (9, 10, 26):
            decisions.append({"source": f"foundry/completion.yaml#{sid}", "decision": gap[:300],
                              "why_founder": "the gap names an authorization or execution-environment decision"})
            continue
        readiness = 2 if row.get("state") == "PARTIAL" else 1
        breadth = max(1, min(3, len(row.get("acceptance", []))))
        existing = row.get("existing") or []
        candidates.append({"id": f"foundry:{sid}", "kind": "foundry", "title": f"Foundry #{sid}: {gap[:160]}",
                           "node": "foundry-55", "reality": row.get("state"), "precursors": existing,
                           "value": 2 * readiness * breadth, "effort": {2: 3, 1: 5}[readiness] + (0 if existing else 1),
                           "score_parts": {"proximity": 2, "readiness": readiness, "breadth": breadth},
                           "source": f"foundry/completion.yaml#{sid}"})
    candidates = sorted(candidates, key=lambda c: (-c["value"], c["effort"], c["id"]))[:MAX_CANDIDATES]
    return {"objective": objective, "founder_decisions": decisions, "candidates": candidates,
            "sources": {"greg/path.json": _sha(path_bytes), "foundry/completion.yaml": _sha(contract_bytes)}}


def previous_dossier(journal, mission_id: str = "") -> dict | None:
    """The latest dossier another First Mission delivered, from receipts retained on the ledger (survives restart)."""
    if journal is None:
        return None
    latest = None
    for event in journal.replay("mission.action"):
        data = event.payload
        if (data.get("capability") == "institution.dossier" and data.get("status") == "DONE"
                and data.get("mission_id") != mission_id and data.get("receipt")):
            latest = data
    if latest is None:
        return None
    record = journal.ledger.find(latest["receipt"])
    output = ((record.payload.get("result") or {}).get("output") or {}) if record is not None else {}
    if not isinstance(output, dict) or "selected" not in output:
        return None
    return {"mission_id": latest["mission_id"], "receipt": latest["receipt"], "selected": list(output["selected"]),
            "value": output.get("value"), "sha256": output.get("sha256"), "lesson": output.get("lesson")}


def survey(params: dict, ctx: InvocationContext) -> dict:
    root = _kernel_root(params, ctx)
    capacity = params.get("effort_budget", 8)
    if not isinstance(capacity, int) or isinstance(capacity, bool) or not 1 <= capacity <= 200:
        raise CapabilityError("effort_budget is a founder-signed integer in [1, 200]")
    state = reconstruct(root, ctx.journal)
    if not state["candidates"]:
        raise CapabilityError("no buildable opportunity is open; every remaining item needs a founder decision")
    return {**state, "kernel_root": str(root), "scoring_model": SCORING_MODEL, "effort_budget": capacity,
            "since_last": previous_dossier(ctx.journal, ctx.mission_id),
            "knapsack": {"values": [c["value"] for c in state["candidates"]],
                         "weights": [c["effort"] for c in state["candidates"]], "capacity": capacity},
            "authority_created": False}


# -- composition -------------------------------------------------------------------------------

def compose_for(candidates: list[dict], root: Path) -> list[dict]:
    """Which existing machinery advances each candidate, and what is missing."""
    import yaml
    from foundry.arsenal import technology
    from foundry.systems import ALTERNATES, SYSTEMS
    from greg.capabilities import BUILTINS
    contract = yaml.safe_load((root / "foundry/completion.yaml").read_bytes())
    module_to_caps = {}
    generic = {"greg/capabilities.py"}          # the default provenance of every builtin says nothing specific
    for cid, (manifest, _) in BUILTINS.items():
        src = (manifest.provenance or {}).get("source", "")
        for part in src.replace(" via ", " ").split():
            module = part.split("uniimente-kernel/")[-1].rstrip("/,;")
            if "/" in module and module not in generic:
                module_to_caps.setdefault(module, set()).add(cid)
    module_to_systems = {}
    for sid, name in SYSTEMS.items():
        module_to_systems.setdefault(f"foundry/systems/{name}.py", set()).add(sid)
    for sid, names in ALTERNATES.items():
        for name in names:
            module_to_systems.setdefault(f"foundry/systems/{name}.py", set()).add(sid)
    out = []
    for c in candidates:
        uses, missing, systems, present = set(), [], set(), []
        if c["kind"] == "foundry":
            sid = int(c["id"].split(":")[1])
            seen, stack = set(), [sid]
            while stack:
                cur = stack.pop()
                for dep in technology(cur).dependencies:
                    if dep not in seen:
                        seen.add(dep)
                        stack.append(dep)
            for dep in sorted(seen):
                (systems.add(dep) if contract.get(dep, {}).get("state") == "COMPLETE"
                 else missing.append(f"Foundry #{dep} ({contract.get(dep, {}).get('state', 'unknown')})"))
        for p in c.get("precursors", []):
            p = str(p).split(" (")[0].strip().rstrip("/")
            if not p or ":" in p:
                continue
            for module, caps in module_to_caps.items():
                if module == p or module.startswith(p + "/"):
                    uses |= caps
            systems |= module_to_systems.get(p, set())
            if (root / p).exists():
                present.append(p)
            else:
                missing.append(f"named precursor {p} is not in this checkout")
        out.append({"candidate": c["id"], "precursor_code_present": present, "uses_capabilities": sorted(uses)[:24],
                    "uses_foundry_systems": sorted(systems), "capability_deficits": missing,
                    "composable_now": not missing and bool(uses or systems or present)})
    return out


def compose(params: dict, ctx: InvocationContext) -> dict:
    root = _kernel_root(params, ctx)
    candidates = params.get("candidates")
    if not isinstance(candidates, list) or not candidates or len(candidates) > MAX_CANDIDATES:
        raise CapabilityError("compose takes the survey's candidate list")
    plans = compose_for(candidates, root)
    return {"plans": plans, "composable": sum(p["composable_now"] for p in plans),
            "deficits": sum(1 for p in plans if p["capability_deficits"]), "authority_created": False}


# -- the deliverable ---------------------------------------------------------------------------

def greedy(values, weights, capacity):
    room, chosen = capacity, []
    for i in sorted(range(len(values)), key=lambda i: (-values[i] / weights[i], i)):
        if weights[i] <= room:
            chosen.append(i)
            room -= weights[i]
    return sorted(chosen)


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def _stem(mission_id) -> str:
    """The dossier file stem: a schema-shaped mission id only, so no parameter can steer the path."""
    import re
    if not isinstance(mission_id, str) or not re.fullmatch(r"m:[a-z0-9][a-z0-9_-]{2,80}", mission_id):
        raise CapabilityError("the dossier is named by a mission id of the form m:<lowercase id>")
    return mission_id.replace(":", "_")


def _render(d: dict) -> str:
    lines = [f"# Founder's First Mission: {d['objective']['title']}", "",
             f"*Reality: sandbox / local. Generated {d['generated_at']} from sources "
             + ", ".join(f"`{k}` {v[:19]}" for k, v in d["sources"].items()) + ". Nothing was sent, published, spent or merged.*", "",
             "## Where you are trying to go", "", f"- Primary node **{d['objective']['node']}**: {d['objective']['outcome']}",
             f"- Gate: {d['objective']['gate']}", "", "## What only you can decide", ""]
    lines += [f"- {_clip(x['decision'], 260)} — *{x['why_founder']}* (`{x['source']}`)" for x in d["founder_decisions"]] or ["- Nothing."]
    lines += ["", "## The highest-value work GREG can advance now", "",
              f"Effort budget {d['selection']['capacity']} units (signed in the mission). Exact selection "
              f"(`{d['selection']['method']}`): value **{d['selection']['value']}** for effort {d['selection']['weight']}. "
              f"Greedy baseline: value {d['selection']['greedy_value']}. "
              + ("The exact method found a strictly better portfolio." if d["selection"]["exact_beats_greedy"]
                 else "Greedy is as good here, so the simpler method's answer stands."), ""]
    for c in d["selected"]:
        plan = c["plan"]
        lines += [f"### {c['title']}", f"- Source `{c['source']}`; reality: {_clip(c['reality'], 200)}",
                  f"- Value {c['value']} ({c['score_parts']}) for effort {c['effort']}",
                  f"- Existing code: {', '.join(plan.get('precursor_code_present', [])[:6]) or 'none named'}",
                  f"- Existing machinery: capabilities {', '.join(plan['uses_capabilities'][:8]) or 'none matched'}; "
                  f"Foundry systems {plan['uses_foundry_systems'] or 'none'}",
                  f"- Capability deficits: {'; '.join(plan['capability_deficits']) or 'none'}", ""]
    lines += ["## Frozen acceptance contract for the next work order", "", "```json",
              json.dumps(d["next_work_order"], indent=1, ensure_ascii=False), "```", "",
              "## How sure this is", "", f"- {d['uncertainty']}", ""]
    s = d.get("since_last")
    lines += ["## What changed since last time", ""] + ([
        f"- Previous First Mission: `{s['previous_mission']}` (receipt `{s['previous_receipt'][:19]}`)",
        f"- Newly selected: {', '.join(s['newly_selected']) or 'none'}",
        f"- No longer selected: {', '.join(s['no_longer_selected']) or 'none'}",
        f"- Still selected: {', '.join(s['still_selected']) or 'none'}",
        f"- Lesson retained then: {s['previous_lesson'] or 'none recorded'}", ""] if s else
        ["- This is the first First Mission on this body; nothing to compare yet.", ""])
    lines += ["## Lesson retained", "", f"- {d['lesson']}", "", "## Next authorized step", "", f"- {d['next_step']}", ""]
    return "\n".join(lines)


def dossier(params: dict, ctx: InvocationContext) -> dict:
    if ctx.deliver_root is None:
        raise CapabilityError("no delivery root is configured; the dossier is delivered to the founder only")
    survey_out, selection, composition = params.get("survey"), params.get("selection"), params.get("composition")
    if not (isinstance(survey_out, dict) and isinstance(selection, dict) and isinstance(composition, dict)):
        raise CapabilityError("dossier binds the survey, the selection and the composition")
    chosen = selection.get("selected")
    cands = survey_out.get("candidates", [])
    if not isinstance(chosen, list) or any(not isinstance(i, int) or not 0 <= i < len(cands) for i in chosen):
        raise CapabilityError("selection indexes do not match the survey's candidates")
    ks = survey_out["knapsack"]
    g = greedy(ks["values"], ks["weights"], ks["capacity"])
    gval = sum(ks["values"][i] for i in g)
    plans = {p["candidate"]: p for p in composition.get("plans", [])}
    selected = [{**cands[i], "plan": plans.get(cands[i]["id"], {"uses_capabilities": [], "uses_foundry_systems": [],
                                                                 "capability_deficits": ["no composition"]})} for i in chosen]
    head = selected[0] if selected else None
    work_order = None if head is None else {
        "order": "advance-" + head["id"].replace(":", "-").replace("_", "-")[:40].lower(),
        "objective": f"Advance '{head['title']}' to its next evidence tier using the existing machinery named in the dossier.",
        "acceptance": {"evidence_tier_before": head["reality"][:120], "must_cite": head["source"],
                       "must_not": ["create authority", "contact anyone", "spend", "publish", "merge"],
                       "verifier": "independent appraisal re-derives the claim from sources"},
        "uses": head["plan"]["uses_capabilities"][:8], "deficits_to_resolve_first": head["plan"]["capability_deficits"]}
    canon_id = params.get("canon_id")
    if canon_id is not None and (not isinstance(canon_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,120}", canon_id)):
        raise CapabilityError("canon_id is a lowercase page name")
    previous = survey_out.get("since_last")
    now_ids = [c["id"] for c in selected]
    since_last = None if not previous else {
        "previous_mission": previous["mission_id"], "previous_receipt": previous["receipt"],
        "newly_selected": [i for i in now_ids if i not in previous["selected"]],
        "no_longer_selected": [i for i in previous["selected"] if i not in now_ids],
        "still_selected": [i for i in now_ids if i in previous["selected"]],
        "previous_lesson": previous.get("lesson")}
    exact_value = sum(ks["values"][i] for i in chosen)
    lesson = (f"With {len(cands)} candidates and an effort budget of {ks['capacity']}, the exact selection gained "
              f"{exact_value - gval} value over the greedy baseline ({exact_value} vs {gval})."
              if exact_value > gval else
              f"With {len(cands)} candidates and an effort budget of {ks['capacity']}, the greedy baseline matched the "
              f"exact optimum ({gval}); the simpler method suffices at this scale.")
    doc = {"kind": "founders-first-mission/1", "mission_id": ctx.mission_id, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "objective": survey_out["objective"], "founder_decisions": survey_out["founder_decisions"],
           "sources": survey_out["sources"], "scoring_model": survey_out["scoring_model"],
           "candidates": [{k: c[k] for k in ("id", "value", "effort")} for c in cands],
           "selection": {"method": "cognition.dp_knapsack (exact; independently verified in the receipt)", "indexes": sorted(chosen),
                         "value": sum(ks["values"][i] for i in chosen), "weight": sum(ks["weights"][i] for i in chosen),
                         "capacity": ks["capacity"], "greedy_indexes": g, "greedy_value": gval,
                         "exact_beats_greedy": sum(ks["values"][i] for i in chosen) > gval},
           "selected": selected, "next_work_order": work_order,
           "uncertainty": ("Scores come from a declared prior over source fields (see scoring_model), not measured value. "
                           "The selection is provably optimal for that model and budget; whether the model ranks real "
                           "value correctly is the open question your review answers."),
           "next_step": ("Review the selection; sign the next work order as a mission to execute it, or change the effort "
                         "budget or the scoring weights and run the mission again. Founder decisions above stay with you."),
           "authority_created": False, "since_last": since_last, "lesson": lesson}
    folder = Path(ctx.deliver_root) / "first-mission"
    folder.mkdir(parents=True, exist_ok=True)
    stem = _stem(ctx.mission_id)
    body = _canon(doc)
    (folder / f"{stem}.json").write_bytes(body)
    (folder / f"{stem}.md").write_text(_render(doc))
    copy = None
    if ctx.workspace is not None:              # a copy inside the mission workspace, so artifact.store may retain it
        Path(ctx.workspace).mkdir(parents=True, exist_ok=True)
        copy = Path(ctx.workspace) / "dossier.json"
        copy.write_bytes(body)
    summary = (f"Primary objective {doc['objective']['node']}: {doc['objective']['title']}. "
               f"Selected under an effort budget of {ks['capacity']}: " + "; ".join(_clip(c["title"], 140) for c in selected)
               + f". {lesson} Founder decisions waiting: {len(doc['founder_decisions'])}. Next: {doc['next_step']}")
    canon = None if canon_id is None else {
        "canon_id": canon_id, "title": _clip("Founder's First Mission: " + doc["objective"]["title"], 250),
        "body": _clip(summary, 4000), "source_refs": [f"{k} {v}" for k, v in doc["sources"].items()] + [f"dossier {_sha(body)}"],
        "rights": "Private founder deliverable generated by GREG from the founder's own repository; not published."}
    return {"delivered": str(folder / f"{stem}.md"), "json": str(folder / f"{stem}.json"), "sha256": _sha(body),
            "selected": now_ids, "value": doc["selection"]["value"], "lesson": lesson,
            "workspace_copy": str(copy) if copy else None, "canon": canon,
            "exact_beats_greedy": doc["selection"]["exact_beats_greedy"], "authority_created": False}


# -- independent appraisal ---------------------------------------------------------------------

def _profit_optimum(values, weights, capacity) -> int:
    """Independent exact optimum: minimum weight per achievable total value (DP over profit, not capacity)."""
    total = sum(values)
    big = 10 ** 15
    minw = [0] + [big] * total
    for v, w in zip(values, weights):
        if v == 0:
            continue
        for t in range(total, v - 1, -1):
            if minw[t - v] + w < minw[t]:
                minw[t] = minw[t - v] + w
    return max(t for t in range(total + 1) if minw[t] <= capacity)


def appraise(params: dict, ctx: InvocationContext) -> dict:
    if ctx.deliver_root is None:
        raise CapabilityError("no delivery root is configured")
    root = _kernel_root(params, ctx)
    stem = _stem(params.get("mission_id") or ctx.mission_id)
    path = Path(ctx.deliver_root) / "first-mission" / f"{stem}.json"
    if not path.is_file():
        return {"verdict": "ABSENT", "findings": ["no dossier delivered yet"], "checked": 0}
    doc = json.loads(path.read_bytes())
    findings, checked = [], 0
    fresh = reconstruct(root, ctx.journal)
    checked += 1
    if fresh["sources"] != doc.get("sources"):
        findings.append("sources changed since the dossier was written (re-run the mission)")
    checked += 1
    if [{k: c[k] for k in ("id", "value", "effort")} for c in fresh["candidates"]] != doc.get("candidates"):
        findings.append("the dossier's candidates do not match a fresh survey of the same sources")
    sel = doc.get("selection") or {}
    values = [c["value"] for c in fresh["candidates"]]
    weights = [c["effort"] for c in fresh["candidates"]]
    idx = sel.get("indexes") or []
    checked += 1
    if any(not isinstance(i, int) or not 0 <= i < len(values) for i in idx) or len(set(idx)) != len(idx):
        findings.append("selection indexes are invalid")
    else:
        weight = sum(weights[i] for i in idx)
        value = sum(values[i] for i in idx)
        checked += 3
        if weight > sel.get("capacity", -1):
            findings.append(f"selection weight {weight} exceeds the signed effort budget {sel.get('capacity')}")
        if value != sel.get("value"):
            findings.append("claimed selection value does not match the candidates")
        optimum = _profit_optimum(values, weights, sel.get("capacity", 0))
        if value != optimum:
            findings.append(f"selection value {value} is not optimal (independent optimum {optimum})")
    checked += 1
    g = greedy(values, weights, sel.get("capacity", 0))
    if g != sel.get("greedy_indexes") or sum(values[i] for i in g) != sel.get("greedy_value"):
        findings.append("the reported greedy baseline does not reproduce")
    checked += 1
    if bool(sel.get("exact_beats_greedy")) != (sel.get("value", 0) > sel.get("greedy_value", 0)):
        findings.append("the exact-versus-greedy claim contradicts its own numbers")
    checked += 1
    md = path.with_suffix(".md")
    if not md.is_file() or doc["objective"]["title"] not in md.read_text():
        findings.append("the founder-readable dossier is missing or does not match its JSON")
    checked += 1
    if doc.get("authority_created") is not False:
        findings.append("the dossier claims authority")
    retained = None
    if params.get("require_retained"):        # the dossier's exact bytes are in the body's content-addressed store
        retained = False
        if ctx.artifact_root is not None:
            from greg.artifacts import ArtifactStore
            try:
                retained = ArtifactStore(Path(ctx.artifact_root)).read(_sha(path.read_bytes())) == path.read_bytes()
            except (CapabilityError, OSError):
                retained = False
    return {"verdict": "VERIFIED" if not findings else "REFUTED", "findings": findings, "checked": checked,
            "retained": retained,
            "dossier_sha256": _sha(path.read_bytes()), "independent_method": "fresh survey + DP over profit + greedy replay"}
