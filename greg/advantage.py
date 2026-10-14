"""Section 13 AdvantageCase: an inspectable case for a consequential proposal, from evidence GREG holds.

Legality, consent, rights and authority are evidence-backed states, never assertions: the absence of a
detected prohibition is ``unresolved``, not permission, and ``supported`` needs provenance and a reviewer.
Hard prohibitions stay outside any score; no scalar leverage score is computed (the supplied multiplicative
formula is not a validated measure). The six outcomes are tracked one by one. The case is composed
deterministically from the inputs of the proposal that carries it, so an appraiser recomputes it; nothing
in it creates authority.
"""
from __future__ import annotations

FIELDS = ("desired_outcome", "bounded_failure", "beneficiaries", "affected_parties", "existing_authority",
          "lawful_options", "smallest_intervention_options", "evidence", "control_point", "expected_benefit",
          "uncertainty", "reusable_assets", "dependencies", "consequence_vector", "reversibility",
          "resource_burden", "strongest_counterexample", "minimum_test", "stop_conditions")
LEGAL_STATES = ("supported", "prohibited", "unresolved", "not_applicable")
LEGAL_QUESTIONS = ("legality", "consent", "rights", "authority")
OUTCOMES = ("evidence", "institutional_leverage", "accountability", "deterrence", "victim_protection",
            "minimal_collateral_harm")
OUTCOME_STATES = ("addressed", "not_applicable", "unresolved")
PROTECTION_FIELDS = ("affected_party", "immediate_harm", "continuing_harm", "retaliation_risk", "privacy_risk",
                     "financial_harm", "reputational_harm", "rights_impact", "evidence_at_risk", "safe_contact_channel",
                     "required_authority", "applicable_notification_duties", "containment_options",
                     "investigation_scope", "restitution_options", "recurrence_controls")
SEQUENCE = ("protect", "preserve", "contain", "investigate", "escalate", "repair", "prevent_recurrence")
NOT_PERMISSION = "no detected prohibition is not permission; a qualified reviewer must supply the state"
VERSION = "greg.advantage/section-13-1"


class AdvantageCaseError(ValueError):
    """The case is missing a field, asserts a state without evidence, or carries a score."""


def legal_state(state: str = "unresolved", *, scope: str | None = None, provenance=(), expires_at: str | None = None,
                reviewer: str | None = None, basis: str | None = None) -> dict:
    """One evidence-backed state. ``supported`` needs provenance and a reviewer; ``prohibited`` needs a basis."""
    if state not in LEGAL_STATES:
        raise AdvantageCaseError(f"legal state must be one of {LEGAL_STATES}, not {state!r}")
    provenance = [str(p) for p in provenance]
    if state == "supported" and (not provenance or not reviewer):
        raise AdvantageCaseError("a supported state needs provenance and a reviewer")
    if state == "prohibited" and not (basis or provenance):
        raise AdvantageCaseError("a prohibited state needs its basis")
    return {"state": state, "scope": scope, "provenance": provenance, "expires_at": expires_at, "reviewer": reviewer,
            "basis": basis if basis is not None else (NOT_PERMISSION if state == "unresolved" else None)}


def outcome(state: str, **detail) -> dict:
    if state not in OUTCOME_STATES:
        raise AdvantageCaseError(f"outcome state must be one of {OUTCOME_STATES}")
    return {"state": state, **detail}


def validate(case: dict) -> dict:
    """Fail closed on a missing field, an unevidenced state, a missing outcome or any scalar score."""
    if not isinstance(case, dict):
        raise AdvantageCaseError("case must be a mapping")
    missing = [f for f in FIELDS if f not in case]
    if missing:
        raise AdvantageCaseError(f"case is missing {missing}")
    legal = case.get("legal")
    if not isinstance(legal, dict) or set(legal) != set(LEGAL_QUESTIONS):
        raise AdvantageCaseError(f"case needs one state for each of {LEGAL_QUESTIONS}")
    for question, record in legal.items():
        legal_state(record["state"], scope=record.get("scope"), provenance=record.get("provenance", ()),
                    expires_at=record.get("expires_at"), reviewer=record.get("reviewer"), basis=record.get("basis"))
    outcomes = case.get("outcomes")
    if not isinstance(outcomes, dict) or set(outcomes) != set(OUTCOMES):
        raise AdvantageCaseError(f"case needs each of the six outcomes {OUTCOMES}")
    for name, record in outcomes.items():
        if record.get("state") not in OUTCOME_STATES:
            raise AdvantageCaseError(f"outcome {name} needs a state in {OUTCOME_STATES}")
    if not isinstance(case.get("prohibitions"), list):
        raise AdvantageCaseError("case needs its list of hard prohibitions, outside any score")
    if case.get("score") is not None or any("score" in k for k in case if k != "score"):
        raise AdvantageCaseError("an AdvantageCase carries no scalar leverage score")
    protection = case.get("protection")
    if protection is not None:
        for party in protection.get("parties", []):
            lacking = [f for f in PROTECTION_FIELDS if f not in party]
            if lacking:
                raise AdvantageCaseError(f"protection case for {party.get('affected_party')!r} lacks {lacking}")
        if tuple(protection.get("sequence", ())) != SEQUENCE:
            raise AdvantageCaseError("protection case must carry the proportionate sequence")
    return case


def _strongest_counterexample(appraisal: dict, assessment: dict) -> dict:
    if appraisal.get("strongest_counterexample"):
        c = appraisal["strongest_counterexample"]
        return {"source": "railscout", "assertion": c["assertion"], "excerpt": c.get("excerpt")}
    challenging = [c for c in appraisal.get("claims", []) if c.get("stance") == "challenges"]
    if challenging:
        c = challenging[0]
        return {"source": "railscout claim " + c["id"], "assertion": c["assertion"], "excerpt": c.get("excerpt")}
    rank = {"high": 3, "medium": 2, "low": 1}
    against = sorted((c for c in assessment.get("cases", []) if c.get("stance") == "against"),
                     key=lambda c: -rank.get(c.get("severity"), 0))
    if against:
        return {"source": "venture engine case " + against[0]["case"], "assertion": against[0]["argument"], "excerpt": None}
    return {"source": "none", "assertion": "no counterexample was supplied by either organ", "excerpt": None}


def _states(appraisal: dict, canonical: dict) -> dict:
    """Legal states come from the appraisal when a reviewer supplied them; otherwise they stay unresolved."""
    supplied = appraisal.get("lawfulness") or {}
    states = {}
    for question in LEGAL_QUESTIONS:
        record = supplied.get(question)
        if isinstance(record, dict):
            states[question] = legal_state(record.get("state", "unresolved"), scope=record.get("scope"),
                                           provenance=record.get("provenance", ()), expires_at=record.get("expires_at"),
                                           reviewer=record.get("reviewer"), basis=record.get("basis"))
        elif question == "authority":
            states[question] = legal_state("unresolved", scope="running the validation step",
                                           basis=f"execution authority {canonical.get('assessment_execution_authority')}; "
                                                 "the memo requires the founder's approval and creates none")
        else:
            states[question] = legal_state("unresolved")
    return states


def _protection(appraisal: dict) -> dict | None:
    parties = appraisal.get("affected_parties") or []
    harmed = [p for p in parties if isinstance(p, dict) and any(p.get(k) for k in PROTECTION_FIELDS[1:9])]
    if not harmed:
        return None
    return {"parties": [{**{f: None for f in PROTECTION_FIELDS}, **p} for p in harmed], "sequence": list(SEQUENCE),
            "professional_decisions": "routed to qualified people through the existing authority path"}


def from_venture(inputs: dict) -> dict:
    """Compose the case for a venture memo from the memo's own receipted inputs; deterministic."""
    appraisal, assessment = inputs["railscout"]["appraisal"], inputs["assessment"]
    packet, canonical, binding = inputs["packet"], inputs["canonical"], inputs["binding"]
    receipts = inputs.get("cognition") or {}
    revenue, conclusion = receipts.get("revenue"), inputs["revenue"]
    sources = appraisal.get("sources", [])
    challenging = [c for c in appraisal.get("claims", []) if c.get("stance") == "challenges"]
    prohibitions = sorted({f"{role} receipt: prohibited consequence declared" for role, r in receipts.items()
                           if ((r.get("consequence_vector") or {}).get("prohibited"))}
                          | {f"{role} receipt: {r['abstention_state']}" for role, r in receipts.items()
                             if r.get("abstention_state") in ("PROHIBITED", "HUMAN_REVIEW_REQUIRED")})
    estimate = None
    if revenue and revenue.get("abstention_state") == "NONE":
        out = revenue["output"]
        estimate = {"low": out["low"], "central": out["central"], "high": out["high"], "units": out.get("units") or {}}
    protection = _protection(appraisal)
    case = {
        "version": VERSION,
        "proposal": {"kind": "venture decision memo", "binding_verdict": binding["verdict"],
                     "engine_verdict": assessment["go_no_go"], "railscout_status": appraisal["status"]},
        "desired_outcome": {"question": appraisal["question"], "transaction": appraisal.get("transaction")},
        "bounded_failure": appraisal.get("failure", {}),
        "beneficiaries": {"buyer": packet.get("audience") or None, "budget_owner": packet.get("buyer_type") or None,
                          "evidenced": bool(packet.get("audience")),
                          "note": "only evidenced parties are named; an unevidenced buyer stays empty"},
        "affected_parties": [p.get("affected_party") if isinstance(p, dict) else p for p in appraisal.get("affected_parties") or []],
        "existing_authority": {"execution_authority": canonical.get("assessment_execution_authority"),
                               "requires_human_approval": True, "decider": "Alfonso Lopez (founder authority)",
                               "created_by_this_memo": "none"},
        "legal": _states(appraisal, canonical),
        "lawful_options": [{"option": step, "legality": "unresolved", "executed": False}
                           for step in assessment.get("validation_plan", [])],
        "smallest_intervention_options": [{"option": "do nothing: retire or park the signal", "cost": "none"},
                                          {"option": appraisal.get("next_action"), "cost": "one bounded validation step"}],
        "evidence": {"sources": [{"id": s["id"], "sha256": s["sha256"], "collected_at": s["collected_at"]} for s in sources],
                     "supporting_claims": sum(c.get("stance") == "supports" for c in appraisal.get("claims", [])),
                     "challenging_claims": len(challenging), "missing": list(appraisal.get("missing", [])),
                     "cognition_receipts": {role: r["receipt_id"] for role, r in receipts.items()}},
        "control_point": {"proof": "RailScout status caps the engine verdict (a score may not outrun missing evidence)",
                          "settlement": "the revenue line is rendered only from GREG's own receipts (a figure may not "
                                        "outrun its causal support)", "binding_rule": binding["why"]},
        "expected_benefit": {"kind": conclusion["kind"], "estimate": estimate, "support": conclusion["why"]},
        "uncertainty": {"missing_evidence": list(appraisal.get("missing", [])),
                        "dominant_variable": ((revenue or {}).get("proof_artifact") or {}).get("dominant_variable"),
                        "causal_support": (receipts.get("causal") or {}).get("abstention_state", "none requested"),
                        "what_changes_the_verdict": inputs["flip"]},
        "reusable_assets": [f"RailScout receipt {inputs['railscout']['receipt_sha256']}", f"wire packet {packet['id']}",
                            *[f"{role} receipt {r['receipt_id']}" for role, r in receipts.items()],
                            f"renderer {inputs['renderer']}"],
        "dependencies": {"railscout_head": inputs["organs"].get("railscout_head"), "wmi_head": inputs["organs"].get("wmi_head"),
                         "cognition_methods": sorted({f"{r['method']} {r['method_version']}" for r in receipts.values()})},
        "consequence_vector": {"consequence_class": "read_only", "executed": "nothing beyond reading sources and running "
                               "both organs", "external_contact": False, "spending": False,
                               "receipt_classes": sorted({r.get("consequence_class", "read_only") for r in receipts.values()})},
        "reversibility": "memo only; the founder can disregard it; receipts stay on the ledger as record",
        "resource_burden": {"organ_processes": 2, "cognition_seconds": round(sum(r.get("latency", 0) for r in receipts.values()), 3),
                            "money_usd": sum(r.get("money_cost", 0) for r in receipts.values())},
        "strongest_counterexample": _strongest_counterexample(appraisal, assessment),
        "minimum_test": appraisal.get("next_action"),
        "stop_conditions": ["RailScout status falls below READY_FOR_HUMAN_REVIEW on re-appraisal",
                            "a prohibited consequence, rights impact or affected-party harm appears",
                            "the appraiser refutes the memo", "the founder declines or stops"],
        "prohibitions": prohibitions,
        "score": None,
        "outcomes": {
            "evidence": outcome("addressed", provenance=f"{len(sources)} source(s) with sha256 and collection time",
                                completeness=f"{len(appraisal.get('missing', []))} missing item(s) named",
                                contradiction_preservation=f"{len(challenging)} challenging claim(s) carried on the wire as risk flags",
                                independent_checks="appraiser re-runs both organs; cognition receipts validated against the ledger",
                                custody="RailScout receipt sha256, manifest sha256, canonical ledger",
                                correction="the verdict-change condition names what evidence would flip it"),
            "institutional_leverage": outcome("addressed", accepting_actor="Alfonso Lopez (founder authority)",
                                              process="signed mission -> delivered memo -> founder decision",
                                              accepted_artifact="this memo, the render of its receipt",
                                              decision_it_can_change=f"whether to run: {appraisal.get('next_action')}"),
            "accountability": outcome("addressed", attributable_decisions=["binding verdict rule", "revenue rule",
                                                                           "RailScout appraisal", "WealthMachine assessment"],
                                      explanation="each verdict carries its rule and the organ outputs it was applied to",
                                      appeal="founder veto; re-appraisal with new sources",
                                      error_correction="a memo that differs from its receipt is REFUTED by the appraiser",
                                      restitution="not applicable: nothing was executed",
                                      preserved_failures="counterevidence and missing evidence are kept in the memo"),
            "deterrence": outcome("not_applicable", detail="a venture memo models no adversary or exploitable "
                                  "opportunity; deterrence belongs to protection cases"),
            "victim_protection": (outcome("addressed", parties=len(protection["parties"]), sequence=list(SEQUENCE))
                                  if protection else outcome("not_applicable", detail="no affected party with declared harm")),
            "minimal_collateral_harm": outcome("addressed", rights_constraints_first=["read-only", "no external contact",
                                                                                      "no spending", "no identification of people"],
                                               exposures=["source bytes read", "two organ processes run",
                                                          "memo stored under the delivery root"],
                                               hidden_in_a_scalar=False),
        },
        "protection": protection,
    }
    return validate(case)


def render(case: dict) -> list[str]:
    """Memo section: every state and outcome visible, no score."""
    legal = "; ".join(f"{q}: **{case['legal'][q]['state']}**" for q in LEGAL_QUESTIONS)
    benefit = case["expected_benefit"]
    estimate = benefit["estimate"]
    shown = (f"{estimate['low']:g} to {estimate['high']:g} (central {estimate['central']:g})" if estimate else "none stated")
    lines = ["## Advantage case (section 13; inspectable, no scalar score)", "",
             f"- Desired outcome: {case['desired_outcome']['question']}",
             f"- Bounded failure: {case['bounded_failure'].get('layer')} — {case['bounded_failure'].get('description')}",
             f"- Beneficiaries: buyer {case['beneficiaries']['buyer'] or 'unevidenced'}; budget owner "
             f"{case['beneficiaries']['budget_owner'] or 'unevidenced'}",
             f"- Affected parties: {', '.join(case['affected_parties']) or 'none declared'}",
             f"- Existing authority: execution {case['existing_authority']['execution_authority']}; decider "
             f"{case['existing_authority']['decider']}; created by this memo: {case['existing_authority']['created_by_this_memo']}",
             f"- States ({NOT_PERMISSION}): {legal}",
             f"- Control point: {case['control_point']['proof']}; {case['control_point']['settlement']}",
             f"- Expected benefit: **{benefit['kind']}** — {shown}; {benefit['support']}",
             f"- Uncertainty: missing {', '.join(case['uncertainty']['missing_evidence']) or 'nothing listed'}; dominant "
             f"variable {case['uncertainty']['dominant_variable']}; causal support {case['uncertainty']['causal_support']}",
             f"- Strongest counterexample ({case['strongest_counterexample']['source']}): {case['strongest_counterexample']['assertion']}",
             f"- Minimum test: {case['minimum_test']}",
             f"- Reversibility: {case['reversibility']}",
             f"- Resource burden: {case['resource_burden']['organ_processes']} organ processes; "
             f"{case['resource_burden']['cognition_seconds']} s cognition; {case['resource_burden']['money_usd']:g} USD",
             f"- Stop conditions: {'; '.join(case['stop_conditions'])}",
             f"- Hard prohibitions (outside any score): {'; '.join(case['prohibitions']) or 'none detected'}",
             "- Six outcomes: " + "; ".join(f"{name} **{case['outcomes'][name]['state']}**" for name in OUTCOMES),
             f"- Case {case['version']}; it creates no authority", ""]
    return lines
