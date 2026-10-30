"""Outcome competence is a replayed projection of canonical receipts and appraisals."""
from __future__ import annotations

import weakref
from fractions import Fraction
from collections import defaultdict
from types import SimpleNamespace

from .contracts import CognitiveReceipt, ProblemGeometry, digest
from . import condition_competence


IDENTITY_VERSION = "signed-claim/1"
IDENTITY_FIELDS = ("identity_version", "mission_id", "command_digest", "check_id", "check_digest",
                   "input_digest", "problem_id", "method", "method_version", "geometry_key")


# Present in every receipt version ever retained (#140 onward).
REQUIRED_RECEIPT_FIELDS = frozenset({"problem_id", "geometry", "method", "input_digest", "output",
                                     "abstention_state", "authority_created"})

def _claim_fields(registration, check, receipt):
    """The registered, signed check defines the claim; a method label does not."""
    return {"identity_version": IDENTITY_VERSION,
            "mission_id": registration["mission_id"], "command_digest": registration["command_digest"],
            "check_id": check["check_id"], "check_digest": digest(check),
            # The signed sensor params, not the receipt's own input digest: a compiled answer's inner request
            # carries the latency its thinking budget allotted, so each re-observation of one claim would hash
            # differently and settle twice. For an uncompiled receipt the two are equal (measured_outcomes checks).
            "input_digest": digest(check["sensor"].get("params", {})), "problem_id": receipt["problem_id"]}


def _outcome_identity(outcome):
    """The claim an outcome settles. A construction's outcome also names the certified answer it settles
    (``answer_version``): two different answers to one signed check are two claims, so a world outcome reported on
    one is never credited to the other, while re-observing one unchanged answer still settles once."""
    fields = {field: outcome[field] for field in IDENTITY_FIELDS}
    if outcome.get("answer_version") is not None:
        fields["answer_version"] = outcome["answer_version"]
    return digest(fields)


def _base_identity(outcome):
    """The signed claim without the answer version: how construction outcomes were keyed before it."""
    return digest({field: outcome[field] for field in IDENTITY_FIELDS})


# Certificate-output fields that describe how an answer was produced, not what it is: re-qualifying the engine at a
# new package version changes them for an unchanged answer (review of #210, S10).
ANSWER_PROVENANCE_FIELDS = ("engine", "composed_of", "authority_created")


def _answer_version(built) -> str:
    """The certified answer a construction receipt carries: the digest of its certificate output without its
    provenance fields (``ANSWER_PROVENANCE_FIELDS``) and without timing, so every re-observation of one unchanged
    answer has the same version, also across an engine upgrade, and a changed answer a new one."""
    result = built.get("result")
    if isinstance(result, dict):
        result = {k: v for k, v in result.items() if k not in ANSWER_PROVENANCE_FIELDS}
    return digest(result)


def _valid_receipt(value):
    if not isinstance(value, dict) or value.get("authority_created") is not False:
        return False
    copy = dict(value)
    identity = copy.pop("receipt_id", None)
    try:
        fields = set(CognitiveReceipt.__dataclass_fields__)
        # Converged #143/#145: retained receipts may predate additive fields (``outcome``,
        # the 0.2 envelope); no unknown field is accepted and the identity digest must hold.
        if identity != digest(copy) or set(copy) - fields or not REQUIRED_RECEIPT_FIELDS <= set(copy):
            return False
        CognitiveReceipt(**copy)
    except (TypeError, ValueError, KeyError):
        return False
    return True


COMPILE_SCHEMAS = ("greg-competency-compilation/0.2",)


def _compiled(value, states=("ANSWERED",)):
    """A retained compile receipt whose selected method answered, or None. Its identity digest must hold, it creates
    no authority, its state is one of ``states``, and the method it executed is credited through its own receipt
    (``selected_receipt``, listed among its intermediate receipts), never through the compiler's label.
    Compositions and abstentions settle nothing here. Competence settles ANSWERED compilations only: a
    WORLD_UNVERIFIED one is a conditional result even when the organ it ran answered NONE."""
    if not isinstance(value, dict) or value.get("schema") not in COMPILE_SCHEMAS:
        return None
    copy = dict(value)
    identity = copy.pop("receipt_id", None)
    if (identity != digest(copy) or value.get("authority_created") is not False or value.get("state") not in states
            or not isinstance(value.get("selected_receipt"), dict)
            or value["selected_receipt"].get("receipt_id") not in value.get("intermediate_receipts", [])):
        return None
    return value


FORMED_SELECTION = "formed_by_capability_genesis"


def _formed_versions(journal) -> set:
    """(capability id, pinned package version) of every installed open-source mechanism Capability Genesis
    registered on this body (``greg.genesis``). A formed mechanism has no BUILTINS entry; it is credited only as
    the identity its own registration pinned."""
    out = set()
    for event in journal.replay("capability.registered"):
        manifest = event.payload.get("manifest") or {}
        if str(manifest.get("provider", "")).startswith("installed:python:") \
                and (event.payload.get("origin") or {}).get("kind") == "package":
            out.add((manifest.get("capability_id"), str((manifest.get("provenance") or {}).get("version"))))
    return out


def _constructed_versions(journal) -> dict:
    """capability id -> pinned version of every construction Capability Genesis registered on this body
    (``greg.recombine``: a ``composed:`` provider with a ``composed`` origin). Its id carries the reduction chain's
    digest, so a construction whose reduction code changed is a different capability and never inherits credit."""
    out = {}
    for event in journal.replay("capability.registered"):
        manifest = event.payload.get("manifest") or {}
        if str(manifest.get("provider", "")).startswith("composed:") \
                and (event.payload.get("origin") or {}).get("kind") == "composed":
            out[manifest.get("capability_id")] = str(manifest.get("version"))
    return out


def _constructed_functions(journal) -> dict:
    """capability id -> the function (``recombine.REDUCTIONS`` key) of every construction Genesis registered here."""
    return {e.payload["manifest"].get("capability_id"): (e.payload.get("origin") or {}).get("function")
            for e in journal.replay("capability.registered")
            if (e.payload.get("origin") or {}).get("kind") == "composed" and e.payload.get("manifest")}


def _constructed(value, constructed):
    """A retained compile receipt that one of this body's constructions answered with its problem-level
    certificate, or None. A construction's answer has no cognitive receipt (``selected_receipt`` is None), so it is
    credited through the compile receipt itself: its identity digest must hold, it creates no authority, it is
    ANSWERED and certified, and the method it names is a construction Genesis registered here. A WORLD_UNVERIFIED
    or abstaining compilation settles nothing, as on every other route."""
    if not isinstance(value, dict) or value.get("schema") not in COMPILE_SCHEMAS:
        return None
    copy = dict(value)
    identity = copy.pop("receipt_id", None)
    if (identity != digest(copy) or value.get("authority_created") is not False or value.get("state") != "ANSWERED"
            or value.get("selected_receipt") is not None
            or value.get("method_or_composition_selected") not in constructed
            or not str(value.get("confidence_type", "")).startswith("certified")):
        return None
    return value


def _constructed_outcome(built, constructed, registration, check, producer, data, event, appraisal):
    """The settled outcome of a construction's answer, under the signed check's identity, or None when the check
    does not bind this receipt (another sensor, producer or input)."""
    if (not check or producer != "cognition.solve" or check["sensor"].get("capability") != producer
            or digest(check["sensor"].get("params", {})) != built["inputs_digest"]):
        return None
    method = built["method_or_composition_selected"]
    cost = built.get("cost") or {}
    return {**_claim_fields(registration, check, built), "receipt": data["receipt"],
            "cognitive_receipt": built["receipt_id"], "method": method, "method_version": constructed[method],
            "answer_version": _answer_version(built),
            "geometry_key": digest({"compiled_geometry": built.get("geometry"),
                                    "subgeometry": built.get("subgeometry"),
                                    "consequence_class": built.get("consequence_class")}),
            "correct": data["passed"], "observation_event": event.event_id, "appraisal_event": appraisal.event_id,
            "cost_usd": float(cost.get("money_usd") or 0.0), "latency": float(built.get("latency_s") or 0.0),
            "causal_credit": "construction: its problem-level certificate, checked independently of its engine",
            "evidence_tier": "locally reobserved and appraised computation; external outcome unproven",
            "authority_created": False, "compile_receipt": built["receipt_id"], "selected_by": "competency_compiler"}


def _known_method(receipt, compiled, builtins, formed) -> bool:
    """The receipt's method is one GREG can credit: a builtin cognitive capability at its manifest version, or,
    for a compiled request the compiler served by a formed mechanism, that mechanism at its pinned version."""
    if compiled is not None and compiled.get("selection_level") == FORMED_SELECTION:
        return (receipt["method"] == compiled.get("method_or_composition_selected")
                and (receipt["method"], receipt["method_version"]) in formed)
    method = builtins.get(receipt["method"], (None,))[0]
    return method is not None and bool(method.cognitive_profile) and method.version == receipt["method_version"]


def _settling_appraisals(journal) -> dict:
    """mission id -> the appraisal under which its observations settle: its latest one, when that is a verified
    success or a verified failure closure (an outcome ledger that heard only successes would score every method by
    its survivors; directive section 11: censored outcomes are not success). Any later other verdict withdraws it.
    A bounded mission's achievement is terminal, so it comes after any failure closure of the same mission: once it
    is recorded, that failure's appraisal no longer settles the mission's observations, and they wait for the
    achievement's own appraisal (TXT-R4-1)."""
    from greg.sop import REQUIRED_CHECKS
    achieved = {e.payload["mission_id"] for e in journal.replay("mission.achieved")}
    latest = {}
    for event in journal.replay("mission.appraised"):
        data = event.payload
        if (data.get("verdict") in ("VERIFIED", "VERIFIED_UNMET")
                and all(data.get("checks", {}).get(k) is True for k in REQUIRED_CHECKS)):
            latest[data["mission_id"]] = event
        else:
            latest.pop(data["mission_id"], None)
    for mid in [m for m, e in latest.items() if e.payload.get("verdict") == "VERIFIED_UNMET" and m in achieved]:
        del latest[mid]
    return latest


def measured_outcomes(journal):
    if journal is None:
        return []
    from .cortex import geometry_key
    from greg.capabilities import BUILTINS
    formed = _formed_versions(journal)
    constructed = _constructed_versions(journal)
    functions = _constructed_functions(journal) if constructed else {}
    world = _world_realizations(journal)
    world_seen = defaultdict(dict)        # claim identity -> objective realizations on any receipt observed for it
    claim_receipts = defaultdict(set)     # claim identity -> the ledger receipts its observations carried
    registrations = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.registered")}
    witnesses = {r.payload["witness_id"]: r.payload for r in journal.ledger.by_type("witness")}
    latest_appraisal, observations = _settling_appraisals(journal), {}
    for event in journal.replay("mission.observed"):
        data = event.payload
        if data.get("mission_id") not in latest_appraisal or not data.get("receipt"):
            continue
        record = journal.ledger.find(data["receipt"])
        if record is None or record.record_type != "receipt":
            continue
        receipt = record.payload.get("result", {}).get("output")
        compiled = _compiled(receipt)
        built = _constructed(receipt, constructed) if compiled is None else None
        if built is not None:             # a construction's certified answer: credited through its compile receipt
            registration = registrations.get(data["mission_id"], {})
            outcome = _constructed_outcome(
                built, constructed, registration,
                next((c for c in registration.get("spec", {}).get("success_checks", [])
                      if c["check_id"] == data["check_id"]), None),
                witnesses.get(record.payload.get("witness_id"), {}).get("capability"),
                data, event, latest_appraisal[data["mission_id"]])
            if outcome is not None:
                identity = _outcome_identity(outcome)
                observations[identity] = outcome
                claim_receipts[identity].add(data["receipt"])
                promise = _promise(built, functions.get(outcome["method"]))
                world_seen[identity].update({e.event_id: e for e in world.get(data["receipt"], {}).values()
                                             if e.payload.get("compile_receipt") == built["receipt_id"]
                                             and promise is not None and _promised(e.payload) == promise})
            continue
        if compiled is not None:
            receipt = compiled["selected_receipt"]
        if (not _valid_receipt(receipt) or receipt["abstention_state"] != "NONE" or
                receipt["evaluator_result"].get("verdict") != "STRUCTURALLY_VERIFIED"):
            continue
        witness = witnesses.get(record.payload.get("witness_id"), {})
        producer = witness.get("capability")
        registration = registrations.get(data["mission_id"], {})
        check = next((c for c in registration.get("spec", {}).get("success_checks", [])
                      if c["check_id"] == data["check_id"]), None)
        if (not _known_method(receipt, compiled, BUILTINS, formed) or
                producer not in ("cognition.solve", receipt["method"]) or not check or
                check["sensor"].get("capability") != producer or
                digest(check["sensor"].get("params", {})) != (compiled or receipt)[
                    "inputs_digest" if compiled else "input_digest"]):
            continue  # an arbitrary adapter's self-labelled receipt is not cognitive competence
        outcome = {**_claim_fields(registration, check, receipt), "receipt": data["receipt"],
                             "cognitive_receipt": receipt["receipt_id"], "method": receipt["method"],
                             "method_version": receipt["method_version"], "geometry_key": geometry_key(ProblemGeometry(**receipt["geometry"])),
                             "correct": data["passed"], "observation_event": event.event_id,
                             "appraisal_event": latest_appraisal[data["mission_id"]].event_id,
                             "cost_usd": receipt["money_cost"], "latency": receipt["latency"],
                             "causal_credit": receipt["causal_credit"],
                             "evidence_tier": "locally reobserved and appraised computation; external outcome unproven",
                             "authority_created": False,
                             **({"compile_receipt": compiled["receipt_id"],
                                 "selected_by": "competency_compiler"} if compiled else {}),
                             **condition_competence.settlement_fields(compiled, check, data["passed"])}
        # Reobservations revise this signed claim; another check/input is not its duplicate.
        observations[_outcome_identity(outcome)] = outcome
    if world_seen:
        order = _realization_order(journal)
        signed = _signed_realizations(journal)
        resolutions, signed_facts = _resolutions(journal, signed), _signed_facts(journal, signed)
        for identity, events in world_seen.items():
            if identity in observations and events:
                facts = sorted(events.values(), key=lambda e: order[e.event_id])
                state = _world_state(facts, resolutions, claim_receipts[identity], signed_facts)
                settled = _world_settled(observations[identity], state)
                if settled is None:
                    observations.pop(identity)    # a live dispute about one answer: scored as neither
                else:
                    observations[identity] = settled
    return list(observations.values())


def competence(journal):
    # Recompute from current evidence instead of trusting a stale settlement cache.
    rows = defaultdict(lambda: {"count": 0, "correct": 0, "cost_usd": 0.0, "latency_seconds": 0.0,
                                "evidence_tier": "local separate-process appraisal"})
    for outcome in measured_outcomes(journal):
        row = rows[outcome["method"], outcome["method_version"], outcome["geometry_key"]]
        row["count"] += 1
        row["correct"] += int(outcome["correct"])
        row["cost_usd"] += outcome["cost_usd"]
        row["latency_seconds"] += outcome["latency"]
    return dict(rows)


def _historical_identity(payload, registrations, observations, journal):
    """Project old records onto claim identities without altering retained bytes.

    Legacy outcome IDs collapsed different inputs. Their exact observation and
    receipt pointers can disambiguate them, even after an appraisal is refuted.
    Unresolvable history retains its old identity and is invalidated, not credited.
    """
    if all(field in payload for field in IDENTITY_FIELDS):
        current = _current_answer_version(payload, journal)
        return _outcome_identity({**payload, "answer_version": current} if current is not None else payload)
    observation = observations.get(payload.get("observation_event"), {})
    registration = registrations.get(observation.get("mission_id"), {})
    check = next((c for c in registration.get("spec", {}).get("success_checks", [])
                  if c["check_id"] == observation.get("check_id")), None)
    record = journal.ledger.find(observation.get("receipt")) if observation.get("receipt") else None
    receipt = record.payload.get("result", {}).get("output") if record is not None and record.record_type == "receipt" else None
    if (check and isinstance(receipt, dict) and registration.get("command_digest") and
            payload.get("mission_id") == observation.get("mission_id") and
            payload.get("receipt") == observation.get("receipt") and
            payload.get("method") == receipt.get("method") and
            payload.get("method_version") == receipt.get("method_version") and
            isinstance(receipt.get("problem_id"), str) and
            digest(check["sensor"].get("params", {})) == receipt.get("input_digest")):
        return _outcome_identity({**payload, **_claim_fields(registration, check, receipt)})
    return payload.get("outcome_id", payload.get("observation_event"))


def _current_answer_version(payload, journal):
    """The answer version the current rule gives a retained construction settlement, re-derived from the compile
    receipt its ledger receipt carries; None when the row has no answer version or its receipt does not hold. A row
    written under an earlier ``_answer_version`` (before S10 dropped the provenance fields) is then the prior of its
    successor, a revision, instead of an orphan that ``reconcile`` invalidates (second review of #219, F1)."""
    if not payload.get("answer_version") or not payload.get("compile_receipt") or not payload.get("receipt"):
        return None
    record = journal.ledger.find(payload["receipt"])
    output = (record.payload.get("result") or {}).get("output") if record is not None and record.record_type == "receipt" else None
    if not isinstance(output, dict) or output.get("receipt_id") != payload["compile_receipt"]:
        return None
    copy = dict(output)
    if copy.pop("receipt_id") != digest(copy):
        return None
    return _answer_version(output)


def reconcile(journal):
    # Append revisions/invalidation. Never silently rewrite historical credit.
    registrations = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.registered")}
    observations = {e.event_id: e.payload for e in journal.replay("mission.observed")}
    outcomes = measured_outcomes(journal)
    measured_ids = {_outcome_identity(o) for o in outcomes}
    every = journal.replay("cognition.settled")
    superseded = {e.payload.get("supersedes") for e in every}          # a merge closure supersedes its shadow too
    settled = [e for e in every if not e.payload.get("merged_into")]
    current, heads = {}, defaultdict(list)
    for event in settled:
        payload = event.payload
        stored = _outcome_identity(payload) if all(f in payload for f in IDENTITY_FIELDS) else None
        # re-derive the answer version only where the stored identity is not measured now (review of #221, F1-b)
        identity = (stored if stored in measured_ids else
                    _historical_identity(payload, registrations, observations, journal))
        identity = identity if identity is not None else event.event_id
        current[identity] = event
        if event.event_id not in superseded and not payload.get("invalidated"):
            heads[identity].append(event)
    # A construction settled before claims named their answer was keyed by its signed claim alone; its successor
    # is the answer-versioned outcome of that claim, which supersedes it instead of appearing beside it.
    legacy = {_base_identity(e.payload): (identity, e) for identity, e in current.items()
              if e.payload.get("compile_receipt") and "answer_version" not in e.payload
              and all(field in e.payload for field in IDENTITY_FIELDS)}
    measured, succeeded, final = {}, set(), {}
    for outcome in outcomes:
        identity = _outcome_identity(outcome)
        outcome = {**outcome, "outcome_id": identity, "evidence_class": "validated_local_computation", "invalidated": False}
        measured[identity] = outcome
        prior = current.get(identity)
        if outcome.get("answer_version") and _base_identity(outcome) in legacy:
            old_identity, legacy_event = legacy[_base_identity(outcome)]
            succeeded.add(old_identity)       # on every pass, so a later pass never invalidates it (review, S5)
            if prior is None:
                prior = legacy_event
        if prior is None or digest({k:v for k,v in prior.payload.items() if k != "supersedes"}) != digest(outcome):
            written = journal.record("cognition.settled", {**outcome, "supersedes": prior.event_id if prior else None},
                                     key=[identity, "revision", digest(outcome), prior.event_id if prior else None],
                                     causal_parent=outcome["observation_event"])
            if getattr(written, "event_id", None):
                final[identity] = written.event_id
    # Chains that an earlier answer-version rule kept apart and the current rule merges (one answer re-observed across
    # an engine-label change, or a body whose earlier pass wrote the new row before invalidating the old head): every
    # live head but the identity's current row is closed, saying so, so no second live row outlasts the claim (review
    # of #221, F1-a; round 3, F1-r3-1). A measured claim's duplicate is merged into this pass's final row (F1-r3-2);
    # an unmeasured claim's is invalidated with it. Merged rows are kept and never read as the claim's settlement.
    for identity, chain_heads in heads.items():
        keep = current[identity].event_id
        for shadow in chain_heads:
            if shadow.event_id == keep:
                continue
            if identity in measured:
                journal.record("cognition.settled", {
                    **shadow.payload, "invalidated": True, "supersedes": shadow.event_id,
                    "merged_into": final.get(identity, keep),
                    "reason": "merged: the same answer under the current answer-version rule; its settlement "
                              "continues in the merged chain"}, key=[identity, "merged", shadow.event_id],
                    causal_parent=shadow.event_id)
            else:
                journal.record("cognition.settled", {
                    **shadow.payload, "invalidated": True, "supersedes": shadow.event_id,
                    "reason": "current appraisal no longer supports competence; a duplicate chain of the claim, "
                              "history retained"}, key=[identity, "invalidate", shadow.event_id],
                    causal_parent=shadow.event_id)
    for identity, prior in current.items():
        if identity not in measured and identity not in succeeded and not prior.payload.get("invalidated"):
            revision = {**prior.payload, "invalidated": True, "supersedes": prior.event_id,
                        "reason": "current appraisal no longer supports competence; history retained"}
            journal.record("cognition.settled", revision, key=[identity, "invalidate", prior.event_id], causal_parent=prior.event_id)


def decisions_to_recheck(journal) -> list[dict]:
    """Compile decisions made while evidence that a resolution later rejected was in force.

    Dependency-aware memory for corrections: a founder-signed resolution rejects facts, and every compile receipt
    retained between the earliest rejected fact and the resolution, that considered the affected method, rested on
    settled competence that no longer holds. It is listed with why, until a later compile of the same problem
    exists. Read-only: it recompiles nothing and changes no decision; the time comparison uses the retained UTC
    stamps of the ledger and the journal."""
    if journal is None:
        return []
    from .compiler import SCHEMA
    facts = {e.event_id: e for e in journal.replay("cognition.realization") if e.payload.get("kind") == "objective"}
    windows = []
    for resolution in _resolutions(journal):
        data = resolution.payload
        rejected = [facts[f] for f in data.get("resolves", []) if f != data.get("accept") and f in facts]
        if rejected:
            windows.append({"method": rejected[0].payload.get("method"), "resolution": resolution.event_id,
                            "start": min(e.occurred_at for e in rejected), "end": resolution.occurred_at,
                            "rejected": sorted(e.event_id for e in rejected)})
    if not windows:
        return []
    compiles = [r for r in journal.ledger.by_type("receipt")
                if isinstance((r.payload.get("result") or {}).get("output"), dict)
                and r.payload["result"]["output"].get("schema") == SCHEMA]
    out = []
    for record in compiles:
        output = record.payload["result"]["output"]
        considered = set(output.get("methods_considered") or []) | {output.get("method_or_composition_selected")}
        hits = [w for w in windows if w["method"] in considered and w["start"] <= record.ts_utc <= w["end"]
                and not any(r.payload["result"]["output"].get("problem_id") == output.get("problem_id")
                            and r.ts_utc > w["end"] for r in compiles)]
        if hits:                          # one row per decision, however many resolutions touched its evidence
            out.append({"receipt": record.hash, "problem_id": output.get("problem_id"),
                        "selected": output.get("method_or_composition_selected"),
                        "affected_methods": sorted({w["method"] for w in hits}),
                        "rejected_events": sorted({f for w in hits for f in w["rejected"]}),
                        "resolution_events": sorted({w["resolution"] for w in hits}),
                        "why": "decided while settled outcomes of the affected method included reports a "
                               "founder-signed resolution later rejected",
                        "recheck_by": "recompile the problem under current evidence (a new signed mission)",
                        "authority_created": False})
    return out


def receipt_links(journal) -> dict:
    """outcome_link and later_appraisal for every settled receipt, as a projection of the canonical journal.

    A receipt is immutable once its identity digest is taken, so its own ``outcome_link`` / ``later_appraisal``
    fields stay as issued; the link lives here, keyed by the cognitive receipt and, for a compiled request, by the
    compile receipt too. The latest settlement decides; an invalidated one links its invalidation. A merge closure
    (F1-a) links its receipts to the chain it merged into, followed to that chain's latest row, so a merged chain's
    receipt reads the claim's current settlement (round 3, R3-N33)."""
    events = journal.replay("cognition.settled")
    by_id = {e.event_id: e for e in events}
    successor = {}
    for event in events:
        if event.payload.get("supersedes"):
            successor[event.payload["supersedes"]] = event.event_id

    def latest(event_id):
        seen = set()
        while event_id in successor and event_id not in seen:
            seen.add(event_id)
            event_id = successor[event_id]
        return by_id.get(event_id)

    def link_of(event):
        data = event.payload
        return {"outcome_link": event.event_id, "later_appraisal": data.get("appraisal_event"),
                "correct": data.get("correct"), "invalidated": bool(data.get("invalidated")),
                "method": data.get("method"), "method_version": data.get("method_version")}

    links = {}
    for event in events:
        data = event.payload
        target = latest(data["merged_into"]) if data.get("merged_into") else None
        link = link_of(target if target is not None else event)
        for key in (data.get("cognitive_receipt"), data.get("compile_receipt")):
            if key:
                links[key] = link
    return links


REALIZATION_SOURCES = ("sensor_observation", "external_record", "founder_reported")
MIN_CALIBRATION_N = 20

# The objective each construction's answer promises (``recombine`` certify outputs): field and sense. A function
# absent here, or an answer with no finite value in that field (an impossible deadline), promises nothing realizable.
OBJECTIVES = {"selection.closure": ("profit", "max"), "selection.budgeted": ("profit", "max"),
              "assignment.staffing": ("staffed", "max"), "assignment.matching": ("size", "max"),
              "project.crash": ("cost", "min")}
# Declared before any outcome and never set per realization: the world fell short of the promise when the realized
# objective is worse than the promised one by more than this fraction of |promised| (at least this much absolute).
REALIZATION_RELATIVE_TOLERANCE = 0.05


def _finite(value) -> bool:
    return type(value) in (int, float) and value == value and abs(value) != float("inf")


def _promise(built, function) -> tuple | None:
    """(objective field, sense, promised value) a construction's certified answer commits to, or None."""
    spec = OBJECTIVES.get(function)
    result = built.get("result") if isinstance(built.get("result"), dict) else {}
    if spec is None or result.get("feasible") is False or not _finite(result.get(spec[0])):
        return None
    return spec[0], spec[1], result[spec[0]]


def _promised(fact) -> tuple:
    return fact.get("objective"), fact.get("sense"), fact.get("promised")


def realization_tolerance(promised) -> float:
    return REALIZATION_RELATIVE_TOLERANCE * max(abs(promised), 1.0)


def world_met(promised, realized, sense) -> bool:
    """Whether the world kept the answer's promise. Wrong in the world means the realized objective is worse than
    promised by more than the declared tolerance (below it for a maximum, above it for a minimum); doing better is
    not a failure. It is evidence about the method on this geometry, not proof the certificate was false: the
    certificate proves the answer from the declared inputs, and the world can still disagree with those inputs."""
    tolerance = realization_tolerance(promised)
    return realized >= promised - tolerance if sense == "max" else realized <= promised + tolerance


def _world_realizations(journal) -> dict:
    """ledger receipt -> {event id: objective realization fact} (``record_realization`` on a construction)."""
    out = defaultdict(dict)
    for event in journal.replay("cognition.realization"):
        if event.payload.get("kind") == "objective":
            out[event.payload["receipt"]][event.event_id] = event
    return out


# Source labels a resolution may accept: a reporter's declaration that the value came from an observation or a record
# outside the reports themselves. GREG does not verify that declaration: ``source`` is whatever the REALIZATION
# command said, so this narrows which reports are eligible, it never makes one verified. A founder-reported value
# is evidence that the founder reported it; a signature proves who said it, not that it is true.
DECLARED_INDEPENDENT_SOURCES = ("sensor_observation", "external_record")
SOURCE_INDEPENDENCE = "declared by the reporter, not verified by GREG"
# The knowledge state of one answer's world outcome. Every fact stays on the record in every state.
WORLD_STATES = ("unreported", "reported", "verdict_concordant", "disputed", "adjudicated", "invalidated")


def _realization_order(journal) -> dict:
    """event id -> position in journal order. Event ids are random (uuid4), so order is never read from them."""
    return {e.event_id: i for i, e in enumerate(journal.replay("cognition.realization"))}


# _signed_realizations memo: ledger -> (records seen, hash of the last one, the verified REALIZATIONs), refreshed
# only when a founder record lands, as goal_gravity._decisions is (second review of #219, F8)
_SIGNED: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()


def _signed_realizations(journal) -> dict:
    """digest -> {body, issued_at, principal} of every REALIZATION command whose retained envelope verifies under
    this body's founder keys (``goal_gravity.founder_facts``: re-derived from the ledger, never trusted from a bare
    ``command.accepted`` record) and that the founder, not a delegated device, signed (F6). A journal with no
    verifiable ledger yields none."""
    try:
        from greg.founder import accepted_body
        from greg.goal_gravity import _founder_record, founder_facts
        ledger = journal.ledger
        records = ledger.records
        cached = _SIGNED.get(ledger)
        if cached is not None:
            seen, tail, out = cached
            if 0 < seen <= len(records) and records[seen - 1].hash == tail \
                    and not any(_founder_record(r) for r in records[seen:]):
                _SIGNED[ledger] = (len(records), records[-1].hash, out)
                return out
        seen, tail = len(records), (records[-1].hash if records else None)
        commands = {d: c for d, c in founder_facts(ledger).signed.items() if c["kind"] == "REALIZATION"}
    except Exception:                     # no body ledger (a bare projection): nothing is signed
        return {}
    out = {d: {"body": accepted_body(c) or {}, "issued_at": str((c.get("envelope") or {}).get("issued_at") or ""),
               "principal": c.get("principal")} for d, c in commands.items() if c.get("principal") == "founder"}
    if seen:
        _SIGNED[ledger] = (seen, tail, out)
    return out


def _instant(issued_at):
    """A signed issued_at as an instant, so stamps that print differently (a whole second has no fraction) still
    order by time, not as strings (F4). An unreadable stamp sorts first; a verified envelope always has one."""
    from greg.founder import instant
    try:
        return instant(issued_at)
    except Exception:
        from datetime import datetime, timezone
        return datetime.min.replace(tzinfo=timezone.utc)


def _signed_body_matches(fact_payload, body, fields) -> bool:
    return isinstance(body, dict) and all(body.get(f) == fact_payload.get(f) for f in fields)


def _resolutions(journal, signed=None) -> list:
    """Founder-signed resolutions, ordered by when the founder signed them (then journal order): realization facts
    of kind ``resolution`` whose command digest names a verified REALIZATION envelope whose signed body is this
    resolution (same receipt, resolves and accept), at most one per signed command. One written any other way,
    or carrying the digest of another signed command, resolves nothing (review of #210, S1); an older-signed
    resolution delivered later never overrides a newer one (S4)."""
    signed = _signed_realizations(journal) if signed is None else signed
    seen, out = set(), []
    for position, event in enumerate(journal.replay("cognition.realization")):
        data = event.payload
        command = signed.get(data.get("command_digest"))
        if (data.get("kind") != "resolution" or command is None or data["command_digest"] in seen
                or not _signed_body_matches(data, command["body"], ("receipt", "resolves", "accept"))):
            continue
        seen.add(data["command_digest"])
        out.append((_instant(command["issued_at"]), position, event))
    return [event for _, _, event in sorted(out, key=lambda item: (item[0], item[1]))]


def _signed_facts(journal, signed=None) -> set:
    """Event ids of objective facts carried by a verified REALIZATION envelope whose signed body is that report
    (receipt, realized, source). Only these are eligible to be accepted by a resolution (review of #210, S9)."""
    signed = _signed_realizations(journal) if signed is None else signed
    return {e.event_id for e in journal.replay("cognition.realization")
            if e.payload.get("kind") == "objective" and e.payload.get("command_digest") in signed
            and _signed_body_matches(e.payload, {"source": "founder_reported",       # Body.apply's default (F7)
                                                 **signed[e.payload["command_digest"]]["body"]},
                                     ("receipt", "realized", "source"))}


def _world_state(facts: list, resolutions: list, receipts, signed_facts=frozenset()) -> dict:
    """The knowledge state of one answer's world outcome, from its objective facts (journal order) and the
    founder-signed resolutions.

    A resolution counts for this answer when it was made on one of the answer's receipts, names only facts about
    this answer, and accepts either nothing (it invalidates the facts it names) or one of them that a verified
    founder-signed REALIZATION carried (``signed_facts``) and whose reporter declared an independent source
    (``DECLARED_INDEPENDENT_SOURCES``; the declaration is not verified). ``resolutions`` come ordered by signing
    time (``_resolutions``). Each fact is ruled by the latest such resolution that names it, so a correction can
    itself be corrected, and a later resolution never revives a fact it does not name. Rejected facts are kept and
    listed; they stop counting.

    unreported: no fact. reported: one value. adjudicated: one value left, held by a fact a resolution accepted
    (an invalidation that leaves an unaccepted report standing adjudicates nothing). invalidated: every
    fact was rejected (the answer awaits a new report). verdict_concordant: the live values differ but every one of
    them gives the same verdict under the declared tolerance, so which is true cannot change competence. disputed:
    the live values give different verdicts: scored as neither until resolved."""
    by_id = {e.event_id: e for e in facts}
    applied, ruling = None, {}            # fact -> True (kept) / False (rejected), by the latest resolution naming it
    for event in resolutions:
        data = event.payload
        named, accept = data.get("resolves") or [], data.get("accept")
        if (data.get("receipt") in receipts and named and set(named) <= set(by_id)
                and (accept is None or (accept in named and accept in signed_facts
                                        and by_id[accept].payload.get("source") in DECLARED_INDEPENDENT_SOURCES))):
            applied = event
            ruling.update({fact: fact == accept for fact in named})
    rejected = {fact for fact, kept in ruling.items() if not kept}
    accepted = {fact for fact, kept in ruling.items() if kept}
    live = [e for e in facts if e.event_id not in rejected]
    values = sorted({e.payload["realized"] for e in live if _finite(e.payload.get("realized"))})
    state = {"live": live, "rejected": sorted(rejected), "values": values,
             "sources": {e.event_id: e.payload.get("source") for e in facts},
             "resolution": applied.event_id if applied is not None else None}
    if not facts:
        return {**state, "state": "unreported"}
    if not values:
        return {**state, "state": "invalidated"}
    if len(values) == 1:
        held_by_acceptance = any(e.event_id in accepted for e in live)
        return {**state, "state": "adjudicated" if held_by_acceptance else "reported"}
    objective, sense, promised = _promised(live[0].payload)
    verdicts = {world_met(promised, v, sense) for v in values}
    return {**state, "state": "verdict_concordant" if len(verdicts) == 1 else "disputed"}


def _world_settled(outcome, state) -> dict | None:
    """The construction outcome as the world settled it; None while its outcome is disputed (scored as neither).

    For competence the world verdict supersedes the certificate's: ``correct`` is true only when the answer passed
    its signed check and the world kept its promise. Both stay on the record (``certificate_correct``, ``world``).
    An unreported or invalidated answer keeps its certificate-only outcome; an invalidated one says so."""
    if state["state"] == "disputed":
        if not outcome["correct"]:        # the signed check failed: wrong whatever the world value (review, S6)
            return {**outcome, "world": {"state": "disputed", "scored": "wrong: the signed check failed, so no "
                                         "reported world value can make the answer right"}}
        return None
    if state["state"] == "unreported":
        return outcome
    if state["state"] == "invalidated":
        return {**outcome, "world": {"state": "invalidated", "rejected_events": state["rejected"],
                                     "resolution_event": state["resolution"]}}
    live = state["live"]
    first = live[0]
    objective, sense, promised = _promised(first.payload)
    values = state["values"]
    met = world_met(promised, values[0], sense)
    realized = values[0] if len(values) == 1 else None
    sources = sorted({e.payload["source"] for e in live})
    return {**outcome, "correct": bool(outcome["correct"] and met), "certificate_correct": outcome["correct"],
            "world": {"state": state["state"], "objective": objective, "sense": sense, "promised": promised,
                      "realized": realized, **({"realized_values": values} if realized is None else {}),
                      "tolerance": realization_tolerance(promised), "met": met, "source": first.payload["source"],
                      "realization_events": sorted(e.event_id for e in live),
                      **({"rejected_events": state["rejected"], "resolution_event": state["resolution"]}
                         if state["resolution"] else {})},
            "evidence_tier": f"realized objective bound to the receipt ({', '.join(sources)}); the certificate "
                             "was checked locally"
                             + ("; a founder-signed resolution accepted a report whose source is "
                                f"{SOURCE_INDEPENDENCE}" if state["state"] == "adjudicated" else "")
                             + ("; the reported values differ but agree on the verdict"
                                if state["state"] == "verdict_concordant" else "")}


def _record_objective(journal, *, receipt, built, realized, source, note, command_digest) -> dict:
    """One fact per report. A repeat of a live report (same receipt, source and value) returns the fact already kept
    when the call is unsigned, or when that fact carries this command or is itself a signed fact; a signed report is
    never absorbed by an unsigned fact, so it is kept as its own (review of #221, F5). The same value under another
    source label is kept as corroboration; a different value is kept as a conflict; a value that only matches a
    rejected fact is a new report. ``_world_state`` decides what the facts do to the claim."""
    promise = _promise(built, _constructed_functions(journal).get(built["method_or_composition_selected"]))
    if promise is None:
        raise ValueError("this construction's answer promises no realizable objective")
    objective, sense, promised = promise
    if not _finite(realized):
        raise ValueError(f"realized takes one finite number: the realized {objective} the answer promised")
    if source not in REALIZATION_SOURCES:
        raise ValueError(f"source is one of {list(REALIZATION_SOURCES)}")
    payload = {"receipt": receipt, "kind": "objective", "compile_receipt": built["receipt_id"],
               "method": built["method_or_composition_selected"], "objective": objective, "sense": sense,
               "promised": promised, "realized": realized, "tolerance": realization_tolerance(promised),
               "tolerance_rule": f"{REALIZATION_RELATIVE_TOLERANCE} x max(|promised|, 1), declared in code",
               "met": world_met(promised, realized, sense), "source": source, "note": str(note)[:300],
               "authority_created": False, **({"command_digest": command_digest} if command_digest else {})}
    existing = [e for e in journal.replay("cognition.realization")
                if e.payload.get("kind") == "objective" and e.payload.get("receipt") == receipt]
    signed = _signed_realizations(journal)
    ruling = {}
    for resolution in _resolutions(journal, signed):
        ruling.update({f: f == resolution.payload.get("accept") for f in resolution.payload.get("resolves") or []})
    live = [e for e in existing if ruling.get(e.event_id, True)]
    signed_facts = _signed_facts(journal, signed) if command_digest else set()
    # A repeat of a live report is idempotent, but a signed report is never absorbed by an unsigned fact with the
    # same source and value (an in-process write, or a fact whose command never reached acceptance): it is kept as
    # its own fact, so it can be accepted (second review of #219, F5).
    same = next((e for e in live if e.payload.get("source") == source and e.payload.get("realized") == realized
                 and (not command_digest or e.payload.get("command_digest") == command_digest
                      or e.event_id in signed_facts)), None)
    if same is not None:
        return same.payload
    # Each new report is its own fact, keyed by source and value (review of #210, S3): a value that matches a rejected
    # fact, or one reported under another source label, is recorded, never deduplicated away.
    key = receipt if not existing else [receipt, "fact", source, repr(realized), len(existing),
                                        *([command_digest] if command_digest else [])]
    agreeing = next((e for e in live if e.payload.get("realized") == realized), None)
    differing = next((e for e in live if e.payload.get("realized") != realized), None)
    payload = {**payload, **({"corroborates": agreeing.event_id} if agreeing is not None else {}),
               **({"conflicts_with": differing.event_id} if differing is not None else {})}
    journal.record("cognition.realization", payload, key=key, sensitivity="confidential")
    return payload


def _claim_facts(seen, world) -> list:
    """The objective facts about one claim's answer, from every receipt that carried it (journal order kept by the
    caller): a fact counts only when it was recorded on that receipt for that compile receipt and promise."""
    return [e for receipt, built, promise, *_ in seen for e in world.get(receipt, {}).values()
            if _promised(e.payload) == promise and e.payload.get("compile_receipt") == built["receipt_id"]]


def record_resolution(journal, *, receipt: str, resolves, accept, note: str, command_digest: str | None,
                      issued_at: str | None = None) -> dict:
    """Resolve a disputed world outcome of one construction answer: a founder-signed, traceable correction.

    ``resolves`` names the recorded facts the resolution rules on, all about the answer carried by ``receipt``.
    ``accept`` is one of them whose reporter declared an independent source (``DECLARED_INDEPENDENT_SOURCES``: the
    label is the reporter's, never verified, so this restricts eligibility and proves nothing), or None, which
    invalidates every named fact (the answer then awaits a new report). An accepting resolution must name every
    live fact whose value differs from the accepted one, or the dispute would stay open behind it. ``note`` states
    the basis. Nothing is deleted: rejected facts stay on the record and stop counting. Only a founder-signed
    REALIZATION command carries it (``command_digest``); settlement ignores one written any other way.

    Resolutions take effect in the order the founder signed them (``issued_at``, then journal order). One signed
    before a resolution already recorded that names any of the same facts is refused with the reason, never applied
    as a silent no-op, so for each fact the resolutions naming it replay in the order they were checked in (second
    review of #219, F4). An equal stamp is accepted: journal order then puts it last, so it takes effect (review of
    #221, G4-d)."""
    if not command_digest:
        raise ValueError("a resolution is a founder-signed REALIZATION command")
    if not isinstance(note, str) or not note.strip():
        raise ValueError("a resolution states its basis in note: what record decides it")
    if (not isinstance(resolves, list) or not resolves or len(set(resolves)) != len(resolves)
            or not all(isinstance(x, str) for x in resolves)):
        raise ValueError("resolves names one or more distinct realization events")
    record = journal.ledger.find(receipt)
    retained = (record.payload.get("result", {}).get("output") if record is not None and
                record.record_type == "receipt" else None)
    constructed = _constructed_versions(journal)
    built = _constructed(retained, constructed) if _compiled(retained) is None else None
    if built is None:
        raise ValueError("resolutions bind only to a certified construction answer")
    world = _world_realizations(journal)
    claim = next((seen for seen in _construction_claims(journal, constructed, _constructed_functions(journal)).values()
                  if receipt in {r for r, *_ in seen}), None)
    if claim is None:
        raise ValueError("no signed check observed this answer, so it has no settled outcome to resolve")
    facts = {e.event_id: e for e in _claim_facts(claim, world)}
    if set(resolves) - set(facts):
        raise ValueError("resolves names only realization facts recorded about this answer")
    signed = _signed_realizations(journal)
    signed_facts = _signed_facts(journal, signed)
    resolutions = _resolutions(journal, signed)
    own = issued_at or (signed.get(command_digest) or {}).get("issued_at")
    if own:
        for prior in resolutions:
            overlap = sorted(set(prior.payload.get("resolves") or []) & set(resolves))
            prior_at = signed[prior.payload["command_digest"]]["issued_at"]
            if overlap and prior.payload["command_digest"] != command_digest and _instant(prior_at) > _instant(own):
                # the instruction first: the rejection record keeps 500 characters and the ingest result 300 (G4-b)
                raise ValueError(f"sign a new resolution if still wanted: this one, signed at {own}, would never take "
                                 f"effect, because a resolution signed later ({prior_at}, event {prior.event_id}) "
                                 f"already rules on {len(overlap)} of its facts, first {overlap[0]}. If a clock was "
                                 "off (the verifier accepts envelopes up to 5 minutes ahead), sign after that time")
    order = _realization_order(journal)   # once, not per fact (F8)
    current = _world_state(sorted(facts.values(), key=lambda e: order[e.event_id]),
                           resolutions, {r for r, *_ in claim}, signed_facts)
    if accept is None:
        # an invalidation must name every live report: one that leaves a report standing would turn that
        # report, never accepted, into the answer's outcome (review of #210, S2)
        standing = [e.event_id for e in current["live"] if e.event_id not in resolves]
        if standing:
            raise ValueError(f"an invalidation names every live report about this answer; still standing: {standing}")
    else:
        if accept not in resolves:
            raise ValueError("accept is one of the facts the resolution names")
        if facts[accept].payload.get("source") not in DECLARED_INDEPENDENT_SOURCES:
            raise ValueError(f"a resolution accepts only a report declared as an independent source "
                             f"({', '.join(DECLARED_INDEPENDENT_SOURCES)}): a signed report proves who reported it, not "
                             "that it is true")
        if accept not in signed_facts:
            raise ValueError("a resolution accepts only a report a verified founder-signed REALIZATION carried")
        kept = facts[accept].payload["realized"]
        unnamed = [e.event_id for e in current["live"] if e.event_id not in resolves and e.payload["realized"] != kept]
        if unnamed:
            raise ValueError(f"name every live report that disagrees with the accepted one: {unnamed}")
    payload = {"receipt": receipt, "kind": "resolution", "compile_receipt": built["receipt_id"],
               "answer_version": _answer_version(built), "resolves": list(resolves), "accept": accept,
               "note": note[:300], "command_digest": command_digest, "authority_created": False}
    key = [receipt, "resolution", sorted(resolves), accept, command_digest]
    kept_event = journal.retained("cognition.realization", key)
    if kept_event is not None:
        return kept_event.payload
    journal.record("cognition.realization", payload, key=key, sensitivity="confidential")
    return payload


def record_realization(journal, *, receipt: str, realized, source: str, note: str = "",
                       command_digest: str | None = None) -> dict:
    """Bind the realized values of a forecast to the ledger receipt that carried it (one fact per receipt).

    ``receipt`` is the ledger hash of the action receipt whose output is the cognitive receipt; ``realized`` is
    one finite number per forecast horizon step, observed after the forecast was made. The source is labelled,
    never upgraded: a founder-reported value is evidence of that report, not a sensor reading. No authority.

    On a construction's certified answer (``_constructed``) ``realized`` is one finite number instead: the realized
    value of the objective the answer promised (``OBJECTIVES``), scored by ``world_met`` and settled once per receipt
    as that method's world outcome on its geometry (``measured_outcomes``)."""
    record = journal.ledger.find(receipt)
    retained = (record.payload.get("result", {}).get("output") if record is not None and
                record.record_type == "receipt" else None)
    cognitive, compiled = _forecast_of(retained)
    if cognitive is None:
        built = _constructed(retained, _constructed_versions(journal))
        if built is None:
            raise ValueError("realizations bind only to a retained, valid, unrefuted forecast receipt or a "
                             "certified construction answer")
        return _record_objective(journal, receipt=receipt, built=built, realized=realized, source=source,
                                 note=note, command_digest=command_digest)
    horizon = len(cognitive["output"]["point"])
    if (not isinstance(realized, list) or len(realized) != horizon
            or not all(type(v) in (int, float) and v == v and abs(v) != float("inf") for v in realized)):
        raise ValueError(f"realized takes {horizon} finite numbers, one per forecast horizon step")
    if source not in REALIZATION_SOURCES:
        raise ValueError(f"source is one of {list(REALIZATION_SOURCES)}")
    payload = {"receipt": receipt, "cognitive_receipt": cognitive["receipt_id"], "realized": list(realized),
               "source": source, "note": str(note)[:300], "authority_created": False,
               **({"compile_receipt": compiled["receipt_id"]} if compiled else {}),
               **({"command_digest": command_digest} if command_digest else {})}
    journal.record("cognition.realization", payload, key=receipt, sensitivity="confidential")
    return payload


USABLE_STATES = ("NONE", "WORLD_UNVERIFIED")   # an answered forecast, or the conditional high-consequence one


def _forecast_receipt(cognitive) -> bool:
    """A retained, valid receipt whose forecast was answered: a refuted, timed-out or abstained receipt keeps its
    output for audit only and is never scored."""
    return (_valid_receipt(cognitive) and cognitive.get("abstention_state") in USABLE_STATES
            and isinstance((cognitive.get("output") or {}).get("quantiles"), dict))


COMPILED_FORECAST_STATES = ("ANSWERED", "WORLD_UNVERIFIED")     # the compile states of USABLE_STATES answers


def _forecast_of(retained) -> tuple:
    """(forecast receipt, compile receipt or None) for a retained receipt, else (None, None). A forecast made
    through the Competency Compiler is the selected method's own receipt inside the compile receipt: it is
    scored as that method's forecast, and the compile receipt is kept as the link."""
    compiled = _compiled(retained, COMPILED_FORECAST_STATES)
    cognitive = compiled["selected_receipt"] if compiled is not None else retained
    if not _forecast_receipt(cognitive):
        return None, None
    return cognitive, compiled


def _forecast_identity(cognitive) -> tuple:
    """One forecast is one (method, version, inputs): re-running it mints a new receipt id (latency is part of
    the receipt), never a new observation."""
    return cognitive["method"], cognitive["method_version"], cognitive["input_digest"]


def _construction_claims(journal, constructed, functions) -> dict:
    """claim identity -> [(ledger receipt, compile receipt, promise, mission id, check passed)], in observation order, for every observation
    ``measured_outcomes`` would credit to a construction once its mission is appraised (the same identity, from
    ``_constructed_outcome``). A construction answer no signed check observed is in no claim: a realization bound to
    it is recorded but never settles."""
    registrations = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.registered")}
    witnesses = {r.payload["witness_id"]: r.payload for r in journal.ledger.by_type("witness")}
    claims = defaultdict(list)
    for event in journal.replay("mission.observed"):
        data = event.payload
        record = journal.ledger.find(data["receipt"]) if data.get("receipt") else None
        if record is None or record.record_type != "receipt":
            continue
        retained = (record.payload.get("result") or {}).get("output")
        built = _constructed(retained, constructed) if _compiled(retained) is None else None
        if built is None:
            continue
        registration = registrations.get(data.get("mission_id"), {})
        check = next((c for c in registration.get("spec", {}).get("success_checks", [])
                      if c["check_id"] == data.get("check_id")), None)
        outcome = _constructed_outcome(built, constructed, registration, check,
                                       witnesses.get(record.payload.get("witness_id"), {}).get("capability"),
                                       data, event, SimpleNamespace(event_id=None))
        promise = _promise(built, functions.get(built["method_or_composition_selected"]))
        if outcome is not None and promise is not None:
            claims[_outcome_identity(outcome)].append((record.hash, built, promise, data["mission_id"],
                                                        bool(data.get("passed"))))
    return claims


def _terminal_missions(journal) -> set:
    """Missions that will never close again: achieved, abandoned or superseded."""
    return ({e.payload["mission_id"] for e in journal.replay("mission.achieved")}
            | {e.payload["mission_id"] for e in journal.replay("mission.lifecycle")
               if e.payload.get("state") in ("ABANDONED", "SUPERSEDED")})


def _awaiting_appraisal(journal) -> set:
    """Missions with a closure no appraisal has judged yet: an achievement with no appraisal of its own (one that
    names no closure_event, as ``Body._close_out`` judges it; an appraisal of an earlier failure or hold names that
    closure, TXT-R4-1), or a held or unmet closure no ``mission.appraised`` names. The body appraises these on a later
    tick."""
    own = {e.payload["mission_id"] for e in journal.replay("mission.appraised") if not e.payload.get("closure_event")}
    judged = {e.payload.get("closure_event") for e in journal.replay("mission.appraised")}
    return ({e.payload["mission_id"] for e in journal.replay("mission.achieved") if e.payload["mission_id"] not in own}
            | {e.payload["mission_id"] for kind in ("mission.held", "mission.unmet") for e in journal.replay(kind)
               if e.event_id not in judged})


def _unsettled_why(verdict, terminal, awaiting=False) -> str:
    """Why a mission's answers earn no competence, said as it is (review of #221, F7-a, F7-b; round 3, G4F7-3)."""
    if awaiting:
        return "pending: a closure of this mission awaits appraisal, so nothing is credited until that appraisal settles"
    if terminal:
        return ("final: the mission ended (abandoned or superseded) without an appraisal, so nothing is credited "
                "for this answer"
                if verdict is None else
                f"final: the mission is closed and its latest appraisal ({verdict}) settles nothing, so nothing is "
                "credited for this answer")
    if verdict is None:
        return "pending: the mission has no closure yet, so nothing is credited until one is appraised"
    return (f"none: the mission's latest appraisal ({verdict}) settles nothing, so nothing is credited until a new "
            "closure is appraised")


def _investigation(identity, seen, state, mission_id, receipts, signed_facts=frozenset(), settles=True,
                   unsettled_why=None) -> dict:
    """A disputed world outcome as actionable work: what is disputed, what evidence would decide it, and whether a
    resolution can be prepared now from evidence already on the record. It prepares; it never signs or applies."""
    live = state["live"]
    first = live[0]
    objective, sense, promised = _promised(first.payload)
    tolerance = realization_tolerance(promised)
    threshold = promised - tolerance if sense == "max" else promised + tolerance
    side = "at or above" if sense == "max" else "at or below"
    reports = [{"event": e.event_id, "realized": e.payload.get("realized"),
                "met": world_met(promised, e.payload["realized"], sense), "receipt": e.payload.get("receipt"),
                "declared_source": e.payload.get("source"), "independence": SOURCE_INDEPENDENCE,
                "signed_command": e.payload.get("command_digest") if e.event_id in signed_facts else None,
                "eligible_to_accept": e.event_id in signed_facts
                and e.payload.get("source") in DECLARED_INDEPENDENT_SOURCES} for e in live]
    independent = sorted({r["realized"] for r in reports if r["eligible_to_accept"]})
    rejected_eligible = sorted(f for f in state.get("rejected", []) if f in signed_facts
                               and state.get("sources", {}).get(f) in DECLARED_INDEPENDENT_SOURCES)
    row = {"kind": "objective_conflict", "world_state": "disputed", "claim": identity, "mission_id": mission_id,
           "method": first.payload.get("method"), "answer_version": _answer_version(seen[-1][1]),
           "objective": objective, "sense": sense, "promised": promised, "realized_values": state["values"],
           "realization_events": sorted(e.event_id for e in live), "receipts_for_claim": receipts,
           "reports": reports, "rejected_events": state["rejected"], "check_passed": seen[-1][4],
           "scored_as": (f"nothing: {unsettled_why or _unsettled_why(None, False)}" if not settles else
                         "neither correct nor wrong: the reported values disagree on the verdict" if seen[-1][4] else
                         "wrong: the signed check failed, so the dispute cannot change this answer's score"),
           "competence_claim": ((unsettled_why or _unsettled_why(None, False)) if not settles else
                                "withheld: no competence is credited for this answer while it is disputed"
                                if seen[-1][4] else "the signed check failed, so the dispute decides nothing about "
                                "this answer's score"),
           "distinguishing_observation": (f"an observation of the realized {objective} for this answer from outside "
                                          f"the disputed reports: "
                                          f"{side} {threshold:g} it kept its promise, otherwise it did not"),
           "acceptable_sources": list(DECLARED_INDEPENDENT_SOURCES), "source_independence": SOURCE_INDEPENDENCE,
           "resolution": "a founder-signed resolution accepting one report declared as an independent source, or "
                         "invalidating the reports; every value stays recorded", "authority_created": False}
    if len(independent) == 1:
        accept = next(r["event"] for r in reports if r["eligible_to_accept"] and r["realized"] == independent[0])
        row["resolvable_now"] = True
        row["prepared_resolution"] = {
            "command": "REALIZATION", "signing": "founder key only; nothing applies until the founder signs it",
            "body": {"receipt": next(r["receipt"] for r in reports if r["event"] == accept),
                     "resolves": [r["event"] for r in reports], "accept": accept,
                     "note": "<basis: the record that decides it, and why its source label can be trusted>"}}
    else:
        row["resolvable_now"] = False
        row["evidence_request"] = {
            "needed": row["distinguishing_observation"],
            "why": ("none of the live reports is a signed report declared as an independent source"
                    + (f" (rejected by a resolution: {rejected_eligible})" if rejected_eligible else "")
                    if not independent else
                    f"the reports declared as independent sources disagree too: {independent}"),
            "how": (f"greg realize {seen[-1][0]} --objective-value <observed> --source external_record "
                    f"--note <reference> --key <founder key>"),
            "acquirable_by_body": [],
            "acquisition_limit": "no capability on this body declares an observation of this world quantity, so "
                                 "GREG asks for the record rather than guessing it"}
    return row


# Above this many co-eligible challengers the preference check reads the pairs and the whole family instead of every
# subset; above this many other disputed methods, or this many joint states of them, it holds them at their current
# counts. Either way the row is marked for investigation with the limit stated, never read as a clean hold (review
# of #221, F2-a, F2-c; round 3, F2R-1, F2R-3).
PREFERENCE_SUBSET_LIMIT = 8
JOINT_DISPUTE_LIMIT = 3
JOINT_STATE_LIMIT = 256
# Above this many evaluations of the compiler's preference rule for one method, the walk stops where it is: a count
# of rule evaluations, so the cut is deterministic, unlike a clock (round 5, W4-1). Changes found before the cut are
# kept; the row is marked for investigation with the limit stated.
PREFERENCE_EVALUATION_LIMIT = 100_000
# How _rank reads a fit with no settled outcome on this body (compiler._rank: competence.get(method, 0.5)).
UNSETTLED_LAPLACE = Fraction(1, 2)


def _resolution_states(n, k, d):
    """Every settled count a method can reach from (n, k) when its d open disputes all resolve: now, and each
    number j of them kept. The compiler's pick is not monotone in the kept count (it breaks Holm ties on rounded p,
    then the name), so the extremes alone can miss a change (review of #221, F2-b)."""
    return [(n, k)] + [(n + d, k + j) for j in range(d + 1)]


def _reachable_states(n, k, d):
    """Every settled count another disputed method can be at while this one's disputes resolve: any a of its d
    disputes resolved, j of them kept (round 3, F2R-1)."""
    return [(n + a, k + j) for a in range(d + 1) for j in range(a + 1)]


def _preference_changes(method, states, counts, joint, inhibit) -> tuple[list[str], list[str]]:
    """Whether the compiler's settled-outcome preference (``compiler._settled_preference``: one-sided Fisher, Holm
    over every co-eligible challenger) can select differently as ``method``'s disputes resolve (``states``), for any
    evidence-ranked first fit, any family of co-eligible fits with enough settled outcomes to be tested, and any
    reachable state of the other disputed methods (``joint``: method -> every count it can be at), settled or not
    (round 4, W4-4). Fits are ordered as ``compiler._rank`` orders them, demoted last (``inhibit``, memoized), so a
    demoted fit is never tested as first (F2-d); the selected fit is the preferred one, or else the first (F2-f).
    The Holm family is the whole co-eligible set, so a pair alone can hide a change (second review of #219, F2). A
    fit demoted at every count it can reach is never a challenger and never first, so it is left out (W4-1).
    Returns the changes found and the limits of the walk; a limit marks the row for investigation but is not itself
    a change found."""
    from itertools import combinations, product
    from .compiler import SETTLED_MIN_N, _settled_preference
    limits = []
    if max(n for n, _ in states) < SETTLED_MIN_N:
        return [], limits
    reach = {m: joint[m] if m in joint else [counts[m]] for m in set(counts) | set(joint) if m != method}
    tested = sorted(m for m, at in reach.items()
                    if max(n for n, _ in at) >= SETTLED_MIN_N and any(inhibit(*s) is None for s in at))
    if len(tested) <= PREFERENCE_SUBSET_LIMIT:
        families = [c for size in range(1, len(tested) + 1) for c in combinations(tested, size)]
    else:
        families = [(m,) for m in tested] + [tuple(tested)]
        limits.append(f"the preference was weighed over pairs and the whole family only: {len(tested)} co-eligible "
                      f"fits exceed the subset limit ({PREFERENCE_SUBSET_LIMIT}), and a family in between could "
                      "select differently")
    others = [m for m in tested if m in joint]
    if len(others) > JOINT_DISPUTE_LIMIT:
        limits.append(f"{len(others)} other disputed methods exceed the joint method limit ({JOINT_DISPUTE_LIMIT}); "
                      "they were held at their current counts, and a joint resolution could select differently")
        others = []
    cut = set()
    spent = [0, False]                              # rule evaluations so far; whether the evaluation limit was hit

    def selected(first, members, world):
        spent[0] += 1
        eligible = [{"method": m, "demoted": inhibit(*world.get(m, (0, 0)))}
                    for m in (first, *sorted(set(members) - {first}))]
        eligible.sort(key=lambda r: 1 if r["demoted"] else 0)        # _rank's leading key; stable otherwise
        top = eligible[0]["method"]
        return (_settled_preference(eligible, world) or {}).get("preferred") or top, top

    found = {}
    for family in families:
        if spent[1]:
            break
        members = (method, *family)
        in_family = [m for m in others if m in members]
        size = 1
        for m in in_family:
            size *= len(joint[m])
        if size > JOINT_STATE_LIMIT:                # per family: only this family's other methods are held (W4-7)
            cut.add((len(in_family), size))
            in_family = []
        for first in members:
            if spent[1]:
                break
            if first in found:
                continue
            for combo in product(*(joint[m] for m in in_family)):
                base = {**counts, **{m: joint[m][0] for m in others if m not in in_family},
                        **dict(zip(in_family, combo))}
                if first != method and inhibit(*base.get(first, (0, 0))):
                    continue                        # a demoted first is ranked last; another fit is first (W4-9)
                if spent[0] + len(states) > PREFERENCE_EVALUATION_LIMIT:
                    spent[1] = True
                    break
                picks = {state: selected(first, members, {**base, method: state}) for state in states}
                if len({pick for pick, _ in picks.values()}) > 1:
                    found[first] = (members, picks, dict(zip(in_family, combo)))
                    break
    if spent[1]:
        limits.append(f"the walk stopped at the evaluation limit ({PREFERENCE_EVALUATION_LIMIT} evaluations of the "
                      "preference rule); the families and states not reached could select differently")
    if cut:
        worst = max(cut, key=lambda c: c[1])
        limits.append(f"a family's {worst[0]} other disputed methods reach {worst[1]} joint states, above the joint "
                      f"state limit ({JOINT_STATE_LIMIT}); in such families they were held at their current counts, "
                      "and a joint resolution could select differently")
    reasons = []
    for first, (members, picks, held) in sorted(found.items()):
        tops = sorted({top for _, top in picks.values()})
        shown = ", ".join(f"{k} of {n} -> {pick}" for (n, k), (pick, _) in picks.items())
        others_at = "; ".join(f"{m} at {k} of {n}" for m, (n, k) in held.items())
        reasons.append(f"the settled-outcome preference with {' or '.join(tops)} ranked first among {sorted(members)} "
                       f"(the compiler's Fisher rule, Holm over that whole family) selects differently as the "
                       f"disputes resolve: {shown}" + (f"; with {others_at}" if others_at else ""))
    return reasons, limits


def _weigh_investigations(journal, rows, settling=None) -> None:
    """Whether resolving each dispute could change a selection the compiler makes from settled outcomes, so the
    work is prioritized by its decision value. Only disputes that a resolution can settle are weighed: the mission
    must hold a settling appraisal (review of #210, S7) and the signed check must have passed (S6). For each method it
    takes every settled count its disputes can resolve to (now, and each number of them kept) and asks, with the
    compiler's own rules, whether any of these differs across them: the inhibition rule, the minimum-evidence floor,
    the settled preference over any family of co-eligible fits with the other disputed methods at any reachable
    count (``_preference_changes``), or the Laplace rank against a settled fit, a reachable value of another
    disputed method, or an unsettled fit (which ``compiler._rank`` reads at 1/2), including a tie, which ``_rank``
    breaks by its later keys (F3). Read-only; an estimate of decision value, since which methods are co-eligible
    depends on the request: where the walk is cut short it says so and errs toward ``investigate``, whose cost is
    one outside record."""
    from functools import lru_cache
    from .compiler import SETTLED_MIN_N, _settled_counts, _settled_inhibition
    inhibit = lru_cache(maxsize=None)(_settled_inhibition)     # one Wilson bound per count, per weighing (F2R-4)
    settling = _settling_appraisals(journal) if settling is None else settling
    counts = _settled_counts(journal)
    weighable = [r for r in rows if r["mission_id"] in settling and r.get("check_passed", True)]
    open_by_method = defaultdict(int)
    for row in weighable:
        open_by_method[row["method"]] += 1
    states = {m: _resolution_states(*counts.get(m, (0, 0)), d) for m, d in open_by_method.items()}
    reachable = {m: _reachable_states(*counts.get(m, (0, 0)), d) for m, d in open_by_method.items()}

    def laplace(pairs):
        return sorted({Fraction(k + 1, n + 2) for n, k in pairs})

    impact = {}
    for method, d in open_by_method.items():
        n, k = counts.get(method, (0, 0))
        low, high = (n + d, k), (n + d, k + d)
        reasons = []
        if len({inhibit(*state) is not None for state in states[method]}) > 1:      # the flag, not its text (W4-3)
            reasons.append("the inhibition rule (demotion) differs between the possible resolutions")
        if n < SETTLED_MIN_N <= n + d:
            reasons.append(f"resolving lifts the method to the {SETTLED_MIN_N}-outcome floor live evidence needs")
        joint = {m: reachable[m] for m in reachable if m != method}
        preference, limits = _preference_changes(method, states[method], counts, joint, inhibit)
        reasons += preference
        own = laplace(states[method])
        lo, hi = own[0], own[-1]
        # Laplace order (it orders fits tied on earlier keys; inclusive, since at a tie later keys decide, F3): a
        # settled fit at its value, another disputed method at each value it can reach (F2-c, exact values rather
        # than their hull, F2R-2), and an unsettled fit at 1/2
        # _rank compares Laplace only within a demotion class, so values of the other class never tie (W4-5)
        classes = {inhibit(*state) is not None for state in states[method]}
        others = [(other, [Fraction(k_o + 1, n_o + 2)]) for other, (n_o, k_o) in sorted(counts.items())
                  if other != method and other not in states and (inhibit(n_o, k_o) is not None) in classes]
        others += [(other, laplace([s for s in reachable[other] if (inhibit(*s) is not None) in classes]))
                   for other in sorted(states) if other != method]
        others = [(other, values) for other, values in others if values]
        if False in classes:
            others.append(("an unsettled co-eligible fit", [UNSETTLED_LAPLACE]))
        for other, values in others:
            inside = [v for v in values if lo <= v <= hi]
            if inside:
                where = (f"{float(values[0]):.3f}" if len(values) == 1 else
                         f"{', '.join(f'{float(v):.3f}' for v in inside[:3])}"
                         + (f" and {len(inside) - 3} more" if len(inside) > 3 else "")
                         + " among the values its own disputes reach")
                reasons.append(f"the Laplace rank against {other} ({where}) flips or ties as the disputes resolve "
                               f"({float(lo):.3f} to {float(hi):.3f}); it orders fits tied on earlier keys")
        impact[method] = {"settled_now": [k, n], "open_disputes": d, "if_all_kept": [high[1], high[0]],
                          "if_all_failed": [low[1], low[0]], "could_change": reasons, "walk_limits": limits,
                          "compared_with": "every other method with settled outcomes on this body, every other "
                                           "disputed method at each count it can reach, and an unsettled fit"}
    for row in rows:
        if row["mission_id"] not in settling:
            row["priority"], row["decision_impact"] = "hold", None
            row["priority_why"] = ("no resolution changes competence now: "
                                   + (row.get("competence_claim") or _unsettled_why(row.get("mission_appraisal"),
                                                                                     False)))
        elif not row.get("check_passed", True):
            row["priority"], row["decision_impact"] = "hold", None
            row["priority_why"] = "the signed check failed: the answer is scored wrong whatever the world value"
        else:
            weighed = impact[row["method"]]
            row["decision_impact"] = weighed
            row["priority"] = "investigate" if weighed["could_change"] or weighed["walk_limits"] else "hold"
            row["priority_why"] = (
                "resolving it can change a selection the compiler makes from settled outcomes"
                if weighed["could_change"] else
                "the walk could not be completed, so a change is not ruled out: " + "; ".join(weighed["walk_limits"])
                if weighed["walk_limits"] else
                "on current evidence no resolution changes a selection rule; it stays recorded and unscored, and is "
                "weighed again as evidence accrues")
        row["cost"] = "one outside record and one founder-signed resolution; no spend, no contact by GREG"


def awaiting_realization(journal) -> list[dict]:
    """Retained forecasts and construction objectives with no realization bound yet.

    A read-only projection of the same receipts accepted by record_realization;
    listing an objective neither verifies its world outcome nor settles it. A construction is listed once per
    signed claim, as ``measured_outcomes`` settles it: a mission that re-observes one answer leaves many receipts
    for one claim, and a report on any of them settles that claim once, so the claim is offered on its latest
    receipt and leaves the list once any of its receipts carries a realization.
    """
    if journal is None:
        return []
    bound = {e.payload["receipt"] for e in journal.replay("cognition.realization")}
    world = _world_realizations(journal)
    constructed = _constructed_versions(journal)
    functions = _constructed_functions(journal)
    settling = _settling_appraisals(journal)
    latest_verdict = {e.payload["mission_id"]: e.payload.get("verdict") for e in journal.replay("mission.appraised")}
    claims = _construction_claims(journal, constructed, functions) if constructed else {}
    terminal = _terminal_missions(journal) if claims else set()
    awaiting = _awaiting_appraisal(journal) if claims else set()
    order = _realization_order(journal) if claims else {}
    signed = _signed_realizations(journal) if claims else {}
    resolutions, signed_facts = (_resolutions(journal, signed), _signed_facts(journal, signed)) if claims else ([], set())
    offered, conflicts = {}, []           # ledger receipt -> (claim identity, receipts, mission id, state); disputes
    for identity, seen in claims.items():
        facts = sorted(_claim_facts(seen, world), key=lambda e: order[e.event_id])
        receipts = {receipt for receipt, *_ in seen}
        mission_id = seen[-1][3]
        state = _world_state(facts, resolutions, receipts, signed_facts)
        if state["state"] in ("unreported", "invalidated"):
            offered[seen[-1][0]] = (identity, len(receipts), mission_id, state)
        elif state["state"] == "disputed":    # _world_settled scores it as neither: say so where reports are made
            row = _investigation(identity, seen, state, mission_id, len(receipts), signed_facts,
                                 settles=mission_id in settling,
                                 unsettled_why=_unsettled_why(latest_verdict.get(mission_id),
                                                              mission_id in terminal, mission_id in awaiting))
            row["mission_appraisal"] = latest_verdict.get(mission_id)
            conflicts.append(row)
    if conflicts:
        _weigh_investigations(journal, conflicts, settling)
    out = []
    for record in journal.ledger.by_type("receipt"):
        retained = (record.payload.get("result") or {}).get("output")
        if record.hash in bound and record.hash not in offered:
            continue
        cognitive, compiled = _forecast_of(retained)
        if cognitive is None:
            if record.hash not in offered:
                continue
            built = _constructed(retained, constructed)
            method = built["method_or_composition_selected"]
            objective, sense, promised = _promise(built, functions.get(method))
            identity, receipts, mission_id, state = offered[record.hash]
            appraised = mission_id in settling
            out.append({"receipt": record.hash, "recorded_at": record.ts_utc, "kind": "objective",
                        "method": method, "method_version": constructed[method],
                        "problem_id": built.get("problem_id"), "compile_receipt": built["receipt_id"],
                        "objective": objective, "sense": sense, "promised": promised,
                        "tolerance": realization_tolerance(promised), "authority_created": False,
                        "claim": identity, "receipts_for_claim": receipts, "mission_id": mission_id,
                        "mission_appraisal": latest_verdict.get(mission_id),
                        "settles": ("once for the claim" if appraised else
                                    "only once the mission's latest appraisal is an eligible settling appraisal "
                                    "(VERIFIED, or VERIFIED_UNMET for a verified failure closure, with the required "
                                    "checks): until then a report is recorded and scores nothing")
                                   + "; a second, different value on any of its receipts is a conflict scored as "
                                     "neither",
                        "world_state": state["state"],
                        **({"invalidated_events": state["rejected"], "resolution_event": state["resolution"]}
                           if state["state"] == "invalidated" else {}),
                        "evidence_limit": "the reported world outcome is not independently verified by this view",
                        "report_with": f"greg realize {record.hash} --objective-value <observed value> --key <founder key>"})
            continue
        out.append({"receipt": record.hash, "recorded_at": record.ts_utc, "method": cognitive["method"],
                    "method_version": cognitive["method_version"], "problem_id": cognitive.get("problem_id"),
                    "horizon": len(cognitive["output"]["point"]),
                    **({"compile_receipt": compiled["receipt_id"]} if compiled else {}),
                    "report_with": f"greg realize {record.hash} --value <v1> ... --value <vH> --key <founder key>"})
    return out + conflicts


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def outcome_calibration(journal, *, alpha: float = 0.05):
    """Coverage of forecast quantiles against realized values bound to their receipts.

    Per method and requested level, the verdict uses the one-step-ahead realization of each forecast only (one
    observation per forecast, so the interval is not inflated by the dependent later steps of the same path).
    One forecast is one (method, version, inputs): re-runs of it count once, and copies that carry different
    realized values are reported as conflicts and left out. A method is MISCALIBRATED when some level's Wilson
    interval at the Bonferroni-corrected level (alpha over 2 x the number of levels) excludes the nominal level,
    so a calibrated forecaster is called miscalibrated with probability at most about alpha, not once per level.
    Each level needs at least MIN_CALIBRATION_N forecasts. Uncorrected 95% intervals, coverage and pinball loss
    over every horizon step are reported as description. Only ``cognition.realization`` facts count."""
    from statistics import NormalDist
    if journal is None:
        return {"verdict": "unmeasured", "n": 0, "missing": "no journal"}
    forecasts, conflicts = {}, []
    for event in journal.replay("cognition.realization"):
        data = event.payload
        record = journal.ledger.find(data["receipt"])
        cognitive, compiled = _forecast_of(record.payload.get("result", {}).get("output")
                                           if record is not None and record.record_type == "receipt" else None)
        if (cognitive is None or cognitive["receipt_id"] != data.get("cognitive_receipt")
                or data.get("compile_receipt") != (compiled["receipt_id"] if compiled else None)):
            continue
        identity = _forecast_identity(cognitive)
        prior = forecasts.get(identity)
        if prior is None:
            forecasts[identity] = (cognitive, list(data["realized"]))
        elif prior[1] != list(data["realized"]) and identity not in conflicts:
            conflicts.append(identity)        # two realizations for one forecast: neither is scored
    for identity in conflicts:
        forecasts.pop(identity, None)
    cells = defaultdict(lambda: {"covered": 0, "n": 0, "pinball": 0.0, "h1_covered": 0, "h1_n": 0})
    for cognitive, realized in forecasts.values():
        quantiles = (cognitive.get("output") or {}).get("quantiles") or {}
        for key, path in quantiles.items():
            level = float(key)
            cell = cells[cognitive["method"], cognitive["method_version"], key]
            if path and realized:
                cell["h1_n"] += 1
                cell["h1_covered"] += int(realized[0] <= path[0])
            for predicted, actual in zip(path, realized):
                cell["n"] += 1
                cell["covered"] += int(actual <= predicted)
                cell["pinball"] += max(level * (actual - predicted), (level - 1) * (actual - predicted))
    conflict_rows = [{"method": m, "method_version": v, "input_digest": d} for m, v, d in conflicts]
    if not cells:
        return {"verdict": "unmeasured", "n": 0, "conflicts": conflict_rows,
                "missing": "receipt-bound realizations of the predicted quantity (cognition.realization)"}
    per_method = defaultdict(int)
    for method, version, _ in cells:
        per_method[method, version] += 1
    levels, verdicts = [], set()
    for (method, version, key), cell in sorted(cells.items()):
        m = per_method[method, version]
        z = NormalDist().inv_cdf(1 - alpha / (2 * m))
        low, high = _wilson(cell["h1_covered"], cell["h1_n"], z)
        nominal = float(key)
        state = ("INSUFFICIENT_EVIDENCE" if cell["h1_n"] < MIN_CALIBRATION_N
                 else "CALIBRATED" if low <= nominal <= high else "MISCALIBRATED")
        verdicts.add(state)
        levels.append({"method": method, "method_version": version, "level": nominal, "receipts": cell["h1_n"],
                       "one_step_coverage": round(cell["h1_covered"] / cell["h1_n"], 4) if cell["h1_n"] else None,
                       "interval_corrected": [round(low, 4), round(high, 4)],
                       "correction": f"Bonferroni over {m} levels, z = {z:.3f}",
                       "interval95_uncorrected": [round(x, 4) for x in _wilson(cell["h1_covered"], cell["h1_n"])],
                       "state": state,
                       "all_steps": {"n": cell["n"], "coverage": round(cell["covered"] / cell["n"], 4),
                                     "mean_pinball": round(cell["pinball"] / cell["n"], 6),
                                     "note": "steps of one path are dependent: description, not a test"}})
    verdict = ("MISCALIBRATED" if "MISCALIBRATED" in verdicts else "INSUFFICIENT_EVIDENCE"
               if "INSUFFICIENT_EVIDENCE" in verdicts else "CALIBRATED")
    return {"verdict": verdict, "n": len(forecasts), "levels": levels, "conflicts": conflict_rows,
            "family_error": f"at most about {alpha} per method version (Bonferroni across its levels)",
            "evidence_tier": "realized values bound to retained forecast receipts; source labelled per fact",
            "authority_created": False}
