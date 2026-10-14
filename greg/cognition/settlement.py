"""Outcome competence is a replayed projection of canonical receipts and appraisals."""
from __future__ import annotations

from collections import defaultdict

from .contracts import CognitiveReceipt, ProblemGeometry, digest


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
            "input_digest": receipt["input_digest"], "problem_id": receipt["problem_id"]}


def _outcome_identity(outcome):
    return digest({field: outcome[field] for field in IDENTITY_FIELDS})


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


def _compiled(value):
    """A retained compile receipt whose selected method answered, or None. Its identity digest must hold, it creates
    no authority, and the method it executed is credited through its own receipt (``selected_receipt``), never
    through the compiler's label. Compositions and abstentions settle nothing here."""
    if not isinstance(value, dict) or value.get("schema") not in COMPILE_SCHEMAS:
        return None
    copy = dict(value)
    identity = copy.pop("receipt_id", None)
    if (identity != digest(copy) or value.get("authority_created") is not False or value.get("state") != "ANSWERED"
            or not isinstance(value.get("selected_receipt"), dict)
            or value["selected_receipt"].get("receipt_id") not in value.get("intermediate_receipts", [])):
        return None
    return value


def measured_outcomes(journal):
    if journal is None:
        return []
    from greg.sop import REQUIRED_CHECKS
    from .cortex import geometry_key
    from greg.capabilities import BUILTINS
    registrations = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.registered")}
    witnesses = {r.payload["witness_id"]: r.payload for r in journal.ledger.by_type("witness")}
    latest_appraisal, observations = {}, {}
    for event in journal.replay("mission.appraised"):
        data = event.payload
        if (data.get("verdict") == "VERIFIED" and all(data.get("checks", {}).get(k) is True for k in REQUIRED_CHECKS)):
            latest_appraisal[data["mission_id"]] = event
        else:
            latest_appraisal.pop(data["mission_id"], None)
    for event in journal.replay("mission.observed"):
        data = event.payload
        if data.get("mission_id") not in latest_appraisal or not data.get("receipt"):
            continue
        record = journal.ledger.find(data["receipt"])
        if record is None or record.record_type != "receipt":
            continue
        receipt = record.payload.get("result", {}).get("output")
        compiled = _compiled(receipt)
        if compiled is not None:
            receipt = compiled["selected_receipt"]
        if (not _valid_receipt(receipt) or receipt["abstention_state"] != "NONE" or
                receipt["evaluator_result"].get("verdict") != "STRUCTURALLY_VERIFIED"):
            continue
        witness = witnesses.get(record.payload.get("witness_id"), {})
        producer = witness.get("capability")
        method = BUILTINS.get(receipt["method"], (None,))[0]
        registration = registrations.get(data["mission_id"], {})
        check = next((c for c in registration.get("spec", {}).get("success_checks", [])
                      if c["check_id"] == data["check_id"]), None)
        if (method is None or not method.cognitive_profile or method.version != receipt["method_version"] or
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
                                 "selected_by": "competency_compiler"} if compiled else {})}
        # Reobservations revise this signed claim; another check/input is not its duplicate.
        observations[_outcome_identity(outcome)] = outcome
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
        return _outcome_identity(payload)
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


def reconcile(journal):
    # Append revisions/invalidation. Never silently rewrite historical credit.
    registrations = {e.payload["mission_id"]: e.payload for e in journal.replay("mission.registered")}
    observations = {e.event_id: e.payload for e in journal.replay("mission.observed")}
    current = {}
    for event in journal.replay("cognition.settled"):
        identity = _historical_identity(event.payload, registrations, observations, journal)
        current[identity if identity is not None else event.event_id] = event
    measured = {}
    for outcome in measured_outcomes(journal):
        identity = _outcome_identity(outcome)
        outcome = {**outcome, "outcome_id": identity, "evidence_class": "validated_local_computation", "invalidated": False}
        measured[identity] = outcome
        prior = current.get(identity)
        if prior is None or digest({k:v for k,v in prior.payload.items() if k != "supersedes"}) != digest(outcome):
            journal.record("cognition.settled", {**outcome, "supersedes": prior.event_id if prior else None},
                           key=[identity, "revision", digest(outcome), prior.event_id if prior else None],
                           causal_parent=outcome["observation_event"])
    for identity, prior in current.items():
        if identity not in measured and not prior.payload.get("invalidated"):
            revision = {**prior.payload, "invalidated": True, "supersedes": prior.event_id,
                        "reason": "current appraisal no longer supports competence; history retained"}
            journal.record("cognition.settled", revision, key=[identity, "invalidate", prior.event_id], causal_parent=prior.event_id)


def receipt_links(journal) -> dict:
    """outcome_link and later_appraisal for every settled receipt, as a projection of the canonical journal.

    A receipt is immutable once its identity digest is taken, so its own ``outcome_link`` / ``later_appraisal``
    fields stay as issued; the link lives here, keyed by the cognitive receipt and, for a compiled request, by the
    compile receipt too. The latest settlement decides; an invalidated one links its invalidation."""
    links = {}
    for event in journal.replay("cognition.settled"):
        data = event.payload
        link = {"outcome_link": event.event_id, "later_appraisal": data.get("appraisal_event"),
                "correct": data.get("correct"), "invalidated": bool(data.get("invalidated")),
                "method": data.get("method"), "method_version": data.get("method_version")}
        for key in (data.get("cognitive_receipt"), data.get("compile_receipt")):
            if key:
                links[key] = link
    return links


REALIZATION_SOURCES = ("sensor_observation", "external_record", "founder_reported")
MIN_CALIBRATION_N = 20


def record_realization(journal, *, receipt: str, realized, source: str, note: str = "",
                       command_digest: str | None = None) -> dict:
    """Bind the realized values of a forecast to the ledger receipt that carried it (one fact per receipt).

    ``receipt`` is the ledger hash of the action receipt whose output is the cognitive receipt; ``realized`` is
    one finite number per forecast horizon step, observed after the forecast was made. The source is labelled,
    never upgraded: a founder-reported value is evidence of that report, not a sensor reading. No authority."""
    record = journal.ledger.find(receipt)
    cognitive = (record.payload.get("result", {}).get("output") if record is not None and
                 record.record_type == "receipt" else None)
    if not _forecast_receipt(cognitive):
        raise ValueError("realizations bind only to a retained, valid, unrefuted forecast receipt")
    horizon = len(cognitive["output"]["point"])
    if (not isinstance(realized, list) or len(realized) != horizon
            or not all(type(v) in (int, float) and v == v and abs(v) != float("inf") for v in realized)):
        raise ValueError(f"realized takes {horizon} finite numbers, one per forecast horizon step")
    if source not in REALIZATION_SOURCES:
        raise ValueError(f"source is one of {list(REALIZATION_SOURCES)}")
    payload = {"receipt": receipt, "cognitive_receipt": cognitive["receipt_id"], "realized": list(realized),
               "source": source, "note": str(note)[:300], "authority_created": False,
               **({"command_digest": command_digest} if command_digest else {})}
    journal.record("cognition.realization", payload, key=receipt, sensitivity="confidential")
    return payload


USABLE_STATES = ("NONE", "WORLD_UNVERIFIED")   # an answered forecast, or the conditional high-consequence one


def _forecast_receipt(cognitive) -> bool:
    """A retained, valid receipt whose forecast was answered: a refuted, timed-out or abstained receipt keeps its
    output for audit only and is never scored."""
    return (_valid_receipt(cognitive) and cognitive.get("abstention_state") in USABLE_STATES
            and isinstance((cognitive.get("output") or {}).get("quantiles"), dict))


def _forecast_identity(cognitive) -> tuple:
    """One forecast is one (method, version, inputs): re-running it mints a new receipt id (latency is part of
    the receipt), never a new observation."""
    return cognitive["method"], cognitive["method_version"], cognitive["input_digest"]


def awaiting_realization(journal) -> list[dict]:
    """Retained forecast receipts with no realization bound yet: what the founder (or a sensor) can report."""
    if journal is None:
        return []
    bound = {e.payload["receipt"] for e in journal.replay("cognition.realization")}
    out = []
    for record in journal.ledger.by_type("receipt"):
        cognitive = (record.payload.get("result") or {}).get("output")
        if record.hash in bound or not _forecast_receipt(cognitive):
            continue
        out.append({"receipt": record.hash, "recorded_at": record.ts_utc, "method": cognitive["method"],
                    "method_version": cognitive["method_version"], "problem_id": cognitive.get("problem_id"),
                    "horizon": len(cognitive["output"]["point"]),
                    "report_with": f"greg realize {record.hash} --value <v1> ... --value <vH> --key <founder key>"})
    return out


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
        cognitive = (record.payload.get("result", {}).get("output")
                     if record is not None and record.record_type == "receipt" else None)
        if not _forecast_receipt(cognitive) or cognitive["receipt_id"] != data.get("cognitive_receipt"):
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
