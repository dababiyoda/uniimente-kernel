"""Capability readiness ladder (directive section 32): what each capability has actually reached, with evidence.

    KNOWN -> INSTALLED -> CREDENTIALLED -> GRANTED -> EXERCISED -> VERIFIED

A read-only fold. Every rung is read from a fact GREG already keeps, through the reader that already computes it:

  KNOWN          a manifest is declared: ``greg.capabilities.BUILTINS``, or a capability Genesis formed and registered
                 on the journal (``capability.registered``), which the running body re-registers (Genesis.restore)
  INSTALLED      what the manifest declares it needs is on this body: ``CapabilityManifest.available()`` (platforms and
                 exact binaries, the test AuthorityOffice.precheck applies before every act) and, for an acquired
                 Python package, its pinned distribution and version (``importlib.metadata``; nothing is imported)
  CREDENTIALLED  every credential handle the manifest declares exists BY NAME in the body's SecretBroker
                 (``SecretBroker.names()``); not applicable when it declares none. No value is resolved or returned
  GRANTED        a live founder grant: an ACTIVE, unpaused mission (``MissionBook``) whose founder-signed light cone
                 admits the capability (its pattern, the consequence ceiling, a horizon not yet passed) or which
                 pre-approves a step the engine itself runs as pre-approved (``greg.missions.pre_approved``: that
                 step's action, capability and target, the manifest's consequence class, no cost); and the capability
                 is ATTACHED, attaching being the founder's own activation decision. The Kernel's single-action grants
                 are spent by the one act they authorize, so they are shown as lineage, never as a live grant
  EXERCISED      a positive Gate receipt of its invocation (receipt -> witness -> capability). Refused invocations are
                 counted and shown, never as exercise
  VERIFIED       an independent appraisal (``mission.appraised``, the separate appraiser process) VERIFIED a closure
                 that judged one of its receipts, and no REFUTED appraisal of a closure judging its receipts (a
                 failure closure's included) and no ``routing.outcome`` ineffective verdict for it came later. A
                 REFUTED latest outcome never reads VERIFIED. A receipt the body itself blamed (routing recorded it
                 ineffective, or the mission blamed its action for breaking a check that passed) is never credited by
                 a VERIFIED closure: that closure vouches for the goal and for every receipt's binding, not for that
                 action's effect. VERIFIED_UNMET (a verified failure) and UNAVAILABLE judge no success either way

Rungs are judged each on their own evidence, so a capability can be EXERCISED and VERIFIED while GRANTED is missing
(its mission closed): the first missing rung then names what its next use needs. Counting tools is not success (S32):
the summary counts capabilities per rung so the verified ones are visible, nothing more.

Where an existing reader says something different about the same capability (Mission Control's class, routing's
track record, the body status inventory) the difference is reported under ``disagreements``, never smoothed over.

Nothing here grants, attaches, widens or promotes anything, and it writes nothing.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from fnmatch import fnmatchcase
import importlib.metadata
import re

from greg import routing
from greg.capabilities import BUILTINS, CapabilityError, CapabilityManifest, CapabilityRegistry, STATES
from greg.lightcone import ScopeError, _instant, _rank

RUNGS = ("KNOWN", "INSTALLED", "CREDENTIALLED", "GRANTED", "EXERCISED", "VERIFIED")
REACHED, MISSING, NOT_APPLICABLE = "reached", "missing", "not_applicable"
JUDGING = ("VERIFIED", "REFUTED")   # VERIFIED (of a success closure) credits; REFUTED (of any closure) demotes


def _rung(status: str, evidence=(), why: str | None = None) -> dict:
    return {"status": status, "evidence": list(evidence), **({"why": why} if why else {})}


# -- KNOWN and lifecycle state: the registry the body uses ----------------------------------------------------------

def body_registry(journal):
    """The capability registry a running body holds, rebuilt from data: the built-ins at their catalog state, every
    capability Genesis formed and registered on the journal (as Genesis.restore re-registers them), then every
    recorded state change in ledger order. Adapters are not loaded. Returns (registry, sources, problems)."""
    from greg.cognition.catalog import initial_state
    from greg.genesis import FORMED
    registry, sources, problems = CapabilityRegistry(), {}, []
    for cid, (manifest, _adapter) in sorted(BUILTINS.items()):
        registry.register(manifest, None, state=initial_state(cid))
        sources[cid] = {"source": "builtin", "ref": manifest.provenance.get("source", "greg/capabilities.py")}
    for event in journal.replay("capability.") if journal is not None else ():
        data = event.payload
        if event.type == "greg.capability.registered":
            manifest = data.get("manifest") or {}
            cid = manifest.get("capability_id")
            if cid in BUILTINS or not str(manifest.get("provider", "")).startswith(FORMED):
                continue                              # the body re-registers only what Genesis formed
            try:
                registry.register(CapabilityManifest.from_dict(manifest), None, state=data.get("state", "VERIFIED"))
            except (CapabilityError, TypeError, ValueError) as exc:
                problems.append({"event": event.event_id, "capability_id": cid,
                                 "problem": f"registered manifest not loadable: {type(exc).__name__}"})
                continue
            sources[cid] = {"source": "registered", "ref": event.event_id}
        elif event.type == "greg.capability.state" and data.get("capability_id") in registry.manifests \
                and data.get("state") in STATES:
            registry.set_state(data["capability_id"], data["state"])
    return registry, sources, problems


def _installed(manifest: CapabilityManifest) -> dict:
    ok, why = manifest.available()
    evidence = [{"kind": "platforms", "ref": list(manifest.platforms)}]
    evidence += [{"kind": "binary", "ref": b} for b in manifest.binaries]
    if not ok:
        return _rung(MISSING, evidence, why)
    provider = manifest.provider
    if provider.startswith("installed:python:"):
        name, _, pinned = provider.removeprefix("installed:python:").partition("==")
        try:
            found = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return _rung(MISSING, evidence, f"python distribution {name} is not installed on this body")
        evidence.append({"kind": "python_distribution", "ref": f"{name}=={found}"})
        if pinned and found != pinned:
            return _rung(MISSING, evidence, f"python distribution {name} is {found}; its manifest pins {pinned}")
    return _rung(REACHED, evidence)


def _credentialled(manifest: CapabilityManifest, handles) -> dict:
    declared = list(manifest.credentials)
    if not declared:
        return _rung(NOT_APPLICABLE, why="its manifest declares no credential handle")
    if isinstance(handles, str):                 # the store could not be read: say so, never guess
        return _rung(MISSING, [{"kind": "declared_handle", "ref": h} for h in declared], handles)
    present = [h for h in declared if h in handles]
    missing = [h for h in declared if h not in handles]
    evidence = [{"kind": "stored_handle", "ref": h} for h in present]
    if missing:
        return _rung(MISSING, evidence, "no stored credential named " + ", ".join(missing)
                     + " (greg secret set NAME stores one; only its name is read here)")
    return _rung(REACHED, evidence)


# -- GRANTED: live founder grants -------------------------------------------------------------------------------------

def _live_missions(book, now: datetime) -> list:
    """Open founder-signed missions whose mandate still runs: ACTIVE, not paused by the founder, horizon ahead."""
    if book is None:
        return []
    live = []
    for _mid, m in sorted(book.missions.items()):
        try:
            open_ = m.status == "ACTIVE" and not m.paused and now < _instant(m.cone.horizon)
        except (ScopeError, ValueError):
            open_ = False
        if open_:
            live.append(m)
    return live


def _may_target(pattern: str, prefix: str) -> bool:
    """Whether a cone's target pattern can name a target under a manifest's prefix. Every target the pattern matches
    starts with its literal head (the text before its first wildcard), so the two can meet only if one of head and
    prefix starts with the other."""
    head = re.split(r"[*?\[]", pattern, maxsplit=1)[0]
    return head.startswith(prefix) or prefix.startswith(head)


def _pre_approved(cid: str, manifest: CapabilityManifest, m) -> tuple[list, list]:
    """The steps naming ``cid`` that this signed mission pre-approves as the engine reads a pre-approval
    (``greg.missions.pre_approved``, which admits one step past the cone), and notes on those it would not run so."""
    from greg.missions import pre_approved
    strategies = {s.get("action_id"): s for s in m.spec.get("strategies") or ()}
    steps, notes = [], []
    for p in m.spec.get("pre_approved_steps") or ():
        if p.get("capability") != cid:
            continue
        s = strategies.get(p.get("action_id"))
        if s is not None and s.get("capability") == cid and pre_approved(m.spec, s, manifest) \
                and str(s.get("target", "")).startswith(manifest.target_prefix):
            steps.append(p["action_id"])
        else:
            notes.append(f"{m.mission_id}'s signed pre-approval of {p.get('action_id')} is not one the engine runs as "
                         f"pre-approved (it needs that strategy's own capability, target under "
                         f"{manifest.target_prefix!r} and cost 0, and the manifest's class {manifest.consequence_class})")
    return steps, notes


def _granted(cid: str, manifest: CapabilityManifest, state: str, live: list, issued: list) -> dict:
    grants, notes = [], []
    for m in live:
        steps, refused = _pre_approved(cid, manifest, m)
        notes += refused
        if steps:
            grants.append({"kind": "signed_pre_approval", "ref": m.mission_id, "command": m.command_digest,
                           "steps": steps, "until": m.cone.horizon})
        if not any(fnmatchcase(cid, pattern) for pattern in m.cone.capabilities):
            continue
        if _rank(manifest.consequence_class) > _rank(m.cone.max_consequence_class):
            notes.append(f"{m.mission_id}'s cone names it, but {manifest.consequence_class} exceeds its ceiling "
                         f"{m.cone.max_consequence_class}: each use needs a founder decision")
            continue
        if not any(_may_target(t, manifest.target_prefix) for t in m.cone.targets):
            notes.append(f"{m.mission_id}'s cone names it, but none of its targets {list(m.cone.targets)} can fall "
                         f"under its prefix {manifest.target_prefix!r}")
            continue
        grants.append({"kind": "light_cone", "ref": m.mission_id, "command": m.command_digest,
                       "until": m.cone.horizon})
    lineage = ([{"kind": "kernel_grants_issued", "ref": issued[-1], "count": len(issued),
                 "note": "single-action grants, each spent by the one act it authorized"}] if issued else [])
    if not grants:
        why = "no open founder-signed mission's light cone admits it"
        if notes:
            why += "; " + "; ".join(notes)
        if issued:
            why += f"; {len(issued)} single-action grant(s) were issued for it before, each spent by its one act"
        if state != "ATTACHED":
            why += f"; its lifecycle state is {state}" + (": quarantined after a failure" if state == "QUARANTINED"
                                                         else ": attaching it is the founder's decision")
        return _rung(MISSING, lineage, why)
    if state != "ATTACHED":
        return _rung(MISSING, grants + lineage, f"a live grant names it, but its lifecycle state is {state}: "
                     + ("quarantined after a failure" if state == "QUARANTINED"
                        else "attaching it is the founder's decision"))
    return _rung(REACHED, grants + lineage)


# -- EXERCISED and VERIFIED: receipts and independent appraisals ------------------------------------------------------

def _receipts(journal) -> tuple[dict, dict]:
    """receipt hash -> (capability, positive) from the Gate's own witness; capability -> issued Kernel grant ids."""
    if journal is None:
        return {}, {}
    ledger = journal.ledger
    witnesses = {r.payload.get("witness_id"): r.payload for r in ledger.by_type("witness")}
    receipts = {}
    for r in ledger.by_type("receipt"):
        cid = (witnesses.get(r.payload.get("witness_id")) or {}).get("capability")
        if cid:
            receipts[r.hash] = (cid, (r.payload.get("result") or {}).get("result_class") == "positive")
    issued_ids = {r.payload.get("grant_id") for r in ledger.by_type("event")
                  if r.payload.get("type") == "greg.authority.grant_issued"}
    issued = defaultdict(list)
    for w in witnesses.values():
        if w.get("grant_id") in issued_ids and w.get("capability"):
            issued[w["capability"]].append(w["grant_id"])
    return receipts, issued


def blamed_receipts(journal, book) -> dict:
    """receipt -> why, for each receipted action the body itself blamed: routing recorded it ineffective (executed,
    re-observed, the world unchanged), or its mission blamed the action for breaking a check that passed before it ran
    (``MissionBook``, a blame drift never washes out)."""
    if journal is None:
        return {}
    blamed = {e.payload["receipt"]: "routing recorded it ineffective: " + str(e.payload.get("reason", ""))[:200]
              for e in journal.replay("routing.outcome")
              if e.payload.get("verdict") == "ineffective" and e.payload.get("receipt")}
    regressed = {(mid, aid): why for mid, m in (book.missions.items() if book is not None else ())
                 for aid, why in m.failed.items() if why.startswith("regressed ")}
    for e in journal.replay("mission.action"):
        why = regressed.get((e.payload.get("mission_id"), e.payload.get("action_id")))
        if why and e.payload.get("status") == "DONE" and e.payload.get("receipt"):
            blamed.setdefault(e.payload["receipt"], why[:200])
    return blamed


def verdict_timeline(journal, receipts: dict, blamed: dict | None = None) -> dict:
    """capability -> [(order, verdict, event_id, detail)] for every appraisal that judged one of its receipts, and
    every ineffective routing outcome naming it, in ledger order.

    A closure judges the receipts of every completed action of its mission before it (the appraiser's exactly-once
    and approval checks) and the observation receipts it cites as evidence (its re-derived checks). A VERIFIED
    closure credits none of the ``blamed`` receipts (``blamed_receipts``); a capability whose every receipt there was
    blamed gets an UNCREDITED row, which verifies nothing. A REFUTED closure demotes every receipt it judged."""
    if journal is None:
        return {}
    blamed = blamed or {}
    order = journal.positions("")
    done = defaultdict(list)                      # mission -> [(order, receipt)] of completed actions
    for e in journal.replay("mission.action"):
        if e.payload.get("status") == "DONE" and e.payload.get("receipt"):
            done[e.payload.get("mission_id")].append((order.get(e.event_id, -1), e.payload["receipt"]))
    observed = {e.payload.get("receipt"): e.payload.get("mission_id") for e in journal.replay("mission.observed")
                if e.payload.get("receipt")}
    closures, achieved = {}, defaultdict(list)
    for kind in ("mission.achieved", "mission.held", "mission.unmet"):
        for e in journal.replay(kind):
            closures[e.event_id] = e
            if kind == "mission.achieved":
                achieved[e.payload.get("mission_id")].append(e)
    timeline = defaultdict(list)
    for a in journal.replay("mission.appraised"):
        verdict, mid = a.payload.get("verdict"), a.payload.get("mission_id")
        if verdict not in JUDGING:
            continue
        at = order.get(a.event_id, -1)
        if a.payload.get("closure_event"):
            closure = closures.get(a.payload["closure_event"])
        else:
            prior = [c for c in achieved.get(mid, ()) if order.get(c.event_id, -1) < at]
            closure = prior[-1] if prior else None
        until = order.get(closure.event_id, at) if closure is not None else at
        judged = {r for pos, r in done.get(mid, ()) if pos < until}
        judged |= {r for r in ((closure.payload.get("evidence") or []) if closure is not None else ())
                   if observed.get(r) == mid}
        effect_held = all(a.payload.get("checks", {}).get(c, False) for c in routing.EFFECT_CHECKS)
        failure = a.payload.get("closure") == "unmet" or (closure is not None and closure.type.endswith(".unmet"))
        for cid in sorted({receipts[r][0] for r in judged if r in receipts}):
            mine = sorted(r for r in judged if receipts.get(r, ("",))[0] == cid)
            detail = {"mission_id": mid, "effect_checks_held": effect_held, **({"closure": "unmet"} if failure else {})}
            if verdict == "VERIFIED" and any(r in blamed for r in mine):
                detail["not_credited"] = [{"receipt": r, "why": blamed[r]} for r in mine if r in blamed]
                mine = [r for r in mine if r not in blamed]
                if not mine:
                    timeline[cid].append((at, "UNCREDITED", a.event_id, detail))
                    continue
            timeline[cid].append((at, verdict, a.event_id, {**detail, "receipts": mine}))
    for e in journal.replay("routing.outcome"):
        if e.payload.get("verdict") == "ineffective" and e.payload.get("capability"):
            timeline[e.payload["capability"]].append((order.get(e.event_id, -1), "INEFFECTIVE", e.event_id,
                                                      {"mission_id": e.payload.get("mission_id"),
                                                       "receipt": e.payload.get("receipt")}))
    return {cid: sorted(rows, key=lambda row: row[0]) for cid, rows in timeline.items()}


def _exercised(mine: list) -> dict:
    """``mine``: [(receipt hash, positive)] of one capability, in ledger order."""
    positive = [h for h, ok in mine if ok]
    refused = len(mine) - len(positive)
    if not positive:
        return _rung(MISSING, why=(f"{refused} invocation(s) were receipted, none positive" if refused
                                   else "no Gate receipt of its invocation"))
    return _rung(REACHED, [{"kind": "receipt", "ref": positive[-1], "count": len(positive),
                            **({"refused": refused} if refused else {})}])


def _verified(rows: list) -> dict:
    verified = [r for r in rows if r[1] == "VERIFIED"]
    if not verified:
        uncredited = [r for r in rows if r[1] == "UNCREDITED"]
        why = "no independent appraisal has verified a closure that judged its receipts"
        if uncredited:
            why += ("; " + ", ".join(sorted({r[3]["mission_id"] for r in uncredited})) + "'s closure was verified, "
                    "but its receipts there were ones the body blamed (" + uncredited[-1][3]["not_credited"][0]["why"]
                    + ")")
        return _rung(MISSING, [{"kind": "appraisal", "ref": r[2], "verdict": "VERIFIED", **r[3]} for r in uncredited],
                     why)
    last = verified[-1]
    later = [r for r in rows if r[1] in ("REFUTED", "INEFFECTIVE") and r[0] > last[0]]
    if later:
        latest = later[-1]
        what = ("appraisal REFUTED " + ("a failure closure" if latest[3].get("closure") == "unmet" else "a closure")
                + " of " + latest[3]["mission_id"]
                + (" (its effect checks held)" if latest[3].get("effect_checks_held") else "")
                if latest[1] == "REFUTED" else "routing recorded it ineffective in " + str(latest[3]["mission_id"]))
        return _rung(MISSING, [{"kind": "appraisal", "ref": last[2], "verdict": "VERIFIED", **last[3]},
                               {"kind": "appraisal" if latest[1] == "REFUTED" else "routing_outcome",
                                "ref": latest[2], "verdict": latest[1], **latest[3]}],
                     f"its latest verdict is {latest[1]}: {what}, after the VERIFIED appraisal")
    return _rung(REACHED, [{"kind": "appraisal", "ref": last[2], "verdict": "VERIFIED", **last[3]}])


# -- the ladder ---------------------------------------------------------------------------------------------------------

def ladder(journal, *, secrets, now: datetime | None = None, providers: dict | None = None,
           capabilities=None) -> dict:
    """Every capability's rungs. ``journal`` may be None (a body that never started); ``secrets`` is the body's
    SecretBroker, of which only ``names()`` is called. ``capabilities`` narrows the rows (the summary still covers
    every capability)."""
    from greg.mission_control import _providers, classify_capability
    from greg.missions import MissionBook
    now = now or datetime.now(timezone.utc)
    providers = _providers() if providers is None else providers
    registry, sources, problems = body_registry(journal)
    try:
        names = secrets.names()
        if not all(isinstance(n, str) for n in names):
            raise TypeError("not a mapping of names")
        handles = set(names)
    except (CapabilityError, OSError, ValueError, TypeError) as exc:   # never a value: only the error's type
        handles = f"the secret store could not be read ({type(exc).__name__})"
    book = MissionBook(journal) if journal is not None else None
    live = _live_missions(book, now)
    receipts, issued = _receipts(journal)
    by_capability = defaultdict(list)
    for receipt, (cid, positive) in receipts.items():
        by_capability[cid].append((receipt, positive))
    timeline = verdict_timeline(journal, receipts, blamed_receipts(journal, book))
    record = routing.track_record(journal) if journal is not None else {}
    inventory = {row["capability_id"]: row for row in registry.inventory()}
    rows, disagreements = [], []
    for cid, manifest in sorted(registry.manifests.items()):
        state = registry.state[cid]
        rungs = {"KNOWN": _rung(REACHED, [{"kind": sources[cid]["source"], "ref": sources[cid]["ref"],
                                            "provider": manifest.provider}]),
                 "INSTALLED": _installed(manifest),
                 "CREDENTIALLED": _credentialled(manifest, handles),
                 "GRANTED": _granted(cid, manifest, state, live, issued.get(cid, [])),
                 "EXERCISED": _exercised(by_capability.get(cid, [])),
                 "VERIFIED": _verified(timeline.get(cid, []))}
        reached = [r for r in RUNGS if rungs[r]["status"] == REACHED]
        first = next((r for r in RUNGS if rungs[r]["status"] == MISSING), None)
        klass = classify_capability(inventory[cid], providers)
        track = record.get(cid)
        rows.append({"capability_id": cid, "source": sources[cid]["source"], "provider": manifest.provider,
                     "consequence_class": manifest.consequence_class, "lifecycle_state": state,
                     "mission_control_class": klass["class"], "reached": reached, "first_missing": first,
                     "why": rungs[first]["why"] if first else None, "rungs": rungs,
                     **({"track_record": {**track, "reliability": round(routing.reliability(track), 3)}}
                        if track else {})})
        disagreements += _disagreements(cid, rungs, klass, track, timeline.get(cid, []))
    if any(s["source"] == "registered" for s in sources.values()):
        formed = sorted(cid for cid, s in sources.items() if s["source"] == "registered")
        disagreements.append({"capability_id": None, "readers": ["greg.body.status (Mission Control's capability "
                                                                 "list)", "greg.genesis.Genesis.restore (the running "
                                                                          "body)"],
                              "detail": f"{len(formed)} capability(ies) Genesis registered on the journal are in the "
                                        "running body's registry but not in body.status, which lists only built-ins: "
                                        + ", ".join(formed[:20])})
    summary = {"capabilities": len(rows),
               "reached": {r: sum(1 for row in rows if r in row["reached"]) for r in RUNGS},
               "not_applicable": {r: sum(1 for row in rows if row["rungs"][r]["status"] == NOT_APPLICABLE)
                                  for r in RUNGS},
               "first_missing": {r: sum(1 for row in rows if row["first_missing"] == r) for r in RUNGS}}
    summary["first_missing"]["none"] = sum(1 for row in rows if row["first_missing"] is None)
    wanted = set(capabilities) if capabilities else None
    return {"rungs": list(RUNGS), "summary": summary,
            "capabilities": [row for row in rows if wanted is None or row["capability_id"] in wanted],
            "disagreements": [d for d in disagreements if wanted is None or d["capability_id"] in wanted
                              or d["capability_id"] is None],
            **({"registry_problems": problems} if problems else {}),
            "at": now.isoformat().replace("+00:00", "Z"),
            "scope": "read-only projection of retained facts; grants, attaches and promotes nothing. Counting "
                     "capabilities per rung is not success: VERIFIED is the only rung an independent appraiser stands "
                     "behind",
            "limits": ["CREDENTIALLED reads handle names in the body's file store; a macOS Keychain item the founder "
                       "added is found only when a capability resolves it, so it reads missing here",
                       "INSTALLED checks declared platforms, binaries and pinned Python distributions; it does not run "
                       "the capability, and a formed capability's built source is checked by Genesis at restore",
                       "GRANTED does not read the body-wide PAUSE or STOP, which halt every grant while they stand, nor "
                       "the constitution's policy: a step the cone or a signed pre-approval admits still waits for an "
                       "exact-scope founder DECISION where policy requires a human",
                       "CREDENTIALLED takes the handle names the broker reads; a store that is not a mapping of names "
                       "is reported unreadable, but a list of strings is read as names, as the broker reads it"]}


def _disagreements(cid: str, rungs: dict, klass: dict, track: dict | None, rows: list) -> list:
    out = []
    if klass["class"] == "BLOCKED" and klass["why"].startswith("needs credentials") \
            and rungs["CREDENTIALLED"]["status"] == REACHED:
        out.append({"capability_id": cid, "readers": ["greg.mission_control.classify_capability", "SecretBroker"],
                    "detail": "Mission Control reads it BLOCKED for its declared credentials although the secret "
                              "store holds every declared handle by name"})
    if klass["class"] in ("RUNNABLE", "SPENDS_MONEY") and rungs["INSTALLED"]["status"] == MISSING:
        out.append({"capability_id": cid, "readers": ["greg.mission_control.classify_capability",
                                                      "readiness INSTALLED"],
                    "detail": f"Mission Control reads it {klass['class']}, but {rungs['INSTALLED']['why']}"})
    counted = bool(track) and track.get("verified", 0) > 0 and not track.get("refuted") and not track.get("ineffective")
    verified = rungs["VERIFIED"]["status"] == REACHED
    if counted and not verified:
        out.append({"capability_id": cid, "readers": ["greg.routing.track_record", "readiness VERIFIED"],
                    "detail": "routing counts its verified actions and no refutation, but " + rungs["VERIFIED"]["why"]
                              + " (track_record reads completed actions only, and does not count a refutation "
                                "whose effect checks held)"})
    elif not verified and (track or {}).get("verified") and any(r[1] == "UNCREDITED" for r in rows):
        missions = sorted({r[3]["mission_id"] for r in rows if r[1] == "UNCREDITED"})
        out.append({"capability_id": cid, "readers": ["greg.routing.track_record", "readiness VERIFIED"],
                    "detail": f"routing counts {track['verified']} verified action(s), crediting it with the verified "
                              f"closure of {', '.join(missions)}, although the body blamed its receipt(s) there (routing "
                              "recorded them ineffective, or the mission blamed them for breaking a passing check); "
                              "readiness credits no verified closure to it"})
    elif verified and not (track or {}).get("verified"):
        out.append({"capability_id": cid, "readers": ["greg.routing.track_record", "readiness VERIFIED"],
                    "detail": "an independent appraisal verified a closure that judged its receipts, but routing "
                              "counts no verified action for it (track_record reads completed actions only, not the "
                              "observation receipts a closure cites)"})
    return out


def report(home, *, capabilities=None, now: datetime | None = None) -> dict:
    """The ladder for the body at ``home``, read while it runs (never takes the writer lock)."""
    from greg.body import BodyError, Layout, observe
    from greg.capabilities import SecretBroker
    layout = Layout(home)
    if not layout.config.exists():
        raise BodyError(f"no body at {layout.home}")
    secrets = SecretBroker(layout.secrets)
    if not layout.ledger.exists():
        return ladder(None, secrets=secrets, now=now, capabilities=capabilities)
    with observe(home, actor="spiffe://uniimente.internal/greg/readiness-reader") as journal:
        return ladder(journal, secrets=secrets, now=now, capabilities=capabilities)
