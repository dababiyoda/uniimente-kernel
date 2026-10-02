"""Inert proposal review and selective disclosure on the canonical receipt path.

Custody is checkable here; truth, professional judgment and permission are not
inferred from custody. No institutional acceptance or external action is created.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from .contracts import CognitionError, ConsequenceVector, digest, number, retained_data
from .protection import AffectedParty


STATES = frozenset(("supported", "prohibited", "unresolved", "not_applicable"))
OBLIGATIONS = ("evidence", "institutional_leverage", "accountability", "deterrence",
               "victim_protection", "minimal_collateral_harm")
HASH = re.compile(r"^sha256:[a-f0-9]{64}$")
ID = re.compile(r"^[A-Za-z0-9:_./-]{1,128}$")


def _text(value, name):
    if not isinstance(value, str) or not 1 <= len(value) <= 512:
        raise CognitionError(f"bounded {name} required")
    return value


def _refs(value):
    if not isinstance(value, list) or len(value) > 32 or any(not isinstance(r, str) or not HASH.fullmatch(r) for r in value):
        raise CognitionError("evidence uses bounded canonical digest references, never raw material")
    return value


@dataclass(frozen=True)
class ScopedEvidenceState:
    state: str
    scope: str
    provenance: str
    evidence_refs: list[str]
    reviewer: str | None = None
    jurisdiction: str | None = None
    expires_at: str | None = None

    def __post_init__(self):
        if self.state not in STATES:
            raise CognitionError("unsupported evidence-backed state")
        _text(self.scope, "assessment scope")
        _text(self.provenance, "assessment provenance")
        _refs(self.evidence_refs)
        if self.reviewer is not None:
            _text(self.reviewer, "reviewer reference")
        if self.jurisdiction is not None:
            _text(self.jurisdiction, "jurisdiction scope")
        if self.expires_at is not None:
            from datetime import datetime
            if not isinstance(self.expires_at, str) or datetime.fromisoformat(self.expires_at.replace("Z", "+00:00")).tzinfo is None:
                raise CognitionError("evidence expiry requires an offset-aware timestamp")


def _state(state, scope, refs, provenance="bounded proposal review; not a professional or permission decision"):
    return asdict(ScopedEvidenceState(state, scope, provenance, refs))


def validate_request(data):
    """Reject malformed review data before computation, retrieval or model calls."""
    allowed = {"desired_outcome", "bounded_failure", "beneficiaries", "affected_parties", "evidence_refs",
               "control_point", "reusable_assets", "dependencies", "strongest_counterexample", "minimum_test",
               "stop_conditions", "options", "protection_case", "accepting_actor", "process_ref",
               "requested_remedy", "conflicting_evidence_refs", "authorized_action_record_refs", "deterrence_required"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise CognitionError("unknown proposal review fields; acceptance, legality and raw evidence cannot be asserted")
    for name in ("desired_outcome", "bounded_failure", "control_point", "strongest_counterexample", "minimum_test"):
        _text(data.get(name), name)
    for name in ("beneficiaries", "affected_parties", "reusable_assets", "dependencies", "stop_conditions"):
        values = data.get(name, [])
        if not isinstance(values, list) or len(values) > 32 or any(not isinstance(v, str) or not ID.fullmatch(v) for v in values):
            raise CognitionError(f"{name} requires bounded identifiers, not personal/raw evidence")
    for name in ("evidence_refs", "conflicting_evidence_refs", "authorized_action_record_refs"):
        _refs(data.get(name, []))
    for name in ("accepting_actor", "process_ref"):
        if data.get(name) is not None and (not isinstance(data[name], str) or not ID.fullmatch(data[name])):
            raise CognitionError("institutional actor/process requires an identifier, not acceptance")
    if "requested_remedy" in data:
        _text(data["requested_remedy"], "requested remedy")
    if type(data.get("deterrence_required", False)) is not bool:
        raise CognitionError("deterrence applicability must be boolean")
    options = data.get("options", [])
    if not isinstance(options, list) or len(options) > 16:
        raise CognitionError("at most sixteen supplied proposal options")
    ids = {"do_nothing", "smallest_intervention"}
    for option in options:
        if not isinstance(option, dict) or set(option) - {"id", "description", "consequences", "benefit_range", "benefit_unit", "resource_burden", "resource_unit", "reversibility", "evidence_refs"}:
            raise CognitionError("unknown option field; legality, consent, authority and scalar scores cannot be asserted")
        identity = option.get("id")
        if not isinstance(identity, str) or not ID.fullmatch(identity) or identity in ids:
            raise CognitionError("unique bounded option identity required")
        ids.add(identity)
        _text(option.get("description"), "option description")
        vector = option.get("consequences", {})
        if not isinstance(vector, dict) or vector.get("lawful") is True or vector.get("consent") is True:
            raise CognitionError("a supplied Boolean cannot establish lawfulness or consent")
        ConsequenceVector(**vector)
        _refs(option.get("evidence_refs", []))
        bounds = option.get("benefit_range")
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise CognitionError("conditional benefit range required")
        if number(bounds[0]) > number(bounds[1]):
            raise CognitionError("benefit range must be ordered")
        _text(option.get("benefit_unit"), "benefit unit")
        number(option.get("resource_burden"), low=0)
        _text(option.get("resource_unit"), "resource unit")
        number(option.get("reversibility"), low=0, high=1)
    if data.get("protection_case") is not None:
        protection_case(data["protection_case"])
    retained_data(data)


def protection_case(data):
    """Reuse the existing affected-party contract, adding explicit investigation scope."""
    allowed = set(AffectedParty.__dataclass_fields__) | {"applicable_notification_duties", "investigation_scope"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise CognitionError("unknown protection case fields")
    if "notification_obligations" in data and "applicable_notification_duties" in data:
        raise CognitionError("use one notification-duty field")
    adapted = dict(data)
    scope = adapted.pop("investigation_scope", "unresolved; qualified review within existing authority")
    _text(scope, "investigation scope")
    if "applicable_notification_duties" in adapted:
        adapted["notification_obligations"] = adapted.pop("applicable_notification_duties")
    party = AffectedParty(**adapted)
    if not ID.fullmatch(party.affected_party):
        raise CognitionError("protection uses a party pseudonym reference")
    # Contact channels and duties remain pointers/proposals; this adapter never contacts anyone.
    if party.safe_contact_channel is not None and not ID.fullmatch(party.safe_contact_channel):
        raise CognitionError("safe contact channel must be a protected reference")
    for name in ("notification_obligations", "containment_options", "restitution_options", "recurrence_controls"):
        if any(not ID.fullmatch(value) for value in getattr(party, name)):
            raise CognitionError("protection details use protected process references, not raw evidence")
    out = asdict(party)
    out["applicable_notification_duties"] = out.pop("notification_obligations")
    out["investigation_scope"] = scope
    out["review_state"] = "unresolved"
    out["professional_judgment"] = "qualified authenticated human required"
    priorities = ["protect"] if party.immediate_harm or party.continuing_harm else []
    # These are review priorities derived from supplied harm, never executable actions.
    if party.immediate_harm >= .5:
        priorities.append("contain")
    if party.evidence_at_risk:
        priorities.append("preserve")
    if (party.immediate_harm or party.continuing_harm) and "contain" not in priorities:
        priorities.append("contain")
    out["review_priorities"] = priorities + ["investigate", "escalate", "repair", "prevent_recurrence"]
    return out


def _custody(refs, journal):
    """Read only verified existing history, returning metadata and no record payloads."""
    ledger = journal.ledger if journal is not None else None
    if ledger is not None:
        ok, reason = ledger.verify_chain()
        if not ok:
            raise CognitionError("canonical evidence history invalid: " + reason)
    rows = []
    for ref in sorted(set(refs)):
        record = ledger.find(ref) if ledger is not None else None
        rows.append({"ref": ref, "state": "supported" if record else "unresolved",
                     "scope": "retained record integrity only; no factual truth, acceptance or authority",
                     "record_type": record.record_type if record else None,
                     "sequence": record.seq if record else None, "previous_ref": record.prev_hash if record else None,
                     "sensitivity": record.payload.get("sensitivity", "restricted") if record else "unknown",
                     "raw_material_disclosed": False})
    return rows


def _dominates(a, b):
    # Benefit has its declared unit. Risk dimensions remain separate, never compensated by upside.
    if a["benefit_unit"] != b["benefit_unit"] or a["resource_unit"] != b["resource_unit"]:
        return False
    va, vb = a["consequences"], b["consequences"]
    dimensions = [k for k in va if k not in ("lawful", "consent", "exposure_details")]
    criteria = [a["benefit_range"][0] >= b["benefit_range"][0], a["benefit_range"][1] >= b["benefit_range"][1],
                a["resource_burden"] <= b["resource_burden"], a["reversibility"] >= b["reversibility"],
                *[va[k] <= vb[k] for k in dimensions]]
    strict = (a["benefit_range"] != b["benefit_range"] or a["resource_burden"] != b["resource_burden"] or
              a["reversibility"] != b["reversibility"] or any(va[k] != vb[k] for k in dimensions))
    return all(criteria) and strict


def build_review(data, *, input_digest, consequence_vector, proof_type=None, proof_artifact=None, journal=None):
    validate_request(data)
    _refs([input_digest])
    vector = ConsequenceVector(**consequence_vector)
    refs = list(data.get("evidence_refs", []))
    conflicts = list(data.get("conflicting_evidence_refs", []))
    action_refs = list(data.get("authorized_action_record_refs", []))
    all_refs = refs + conflicts + action_refs + [r for o in data.get("options", []) for r in o.get("evidence_refs", [])]
    custody = _custody(all_refs, journal)
    present = {r["ref"] for r in custody if r["state"] == "supported"}
    evidence_state = "supported" if refs and set(refs) <= present else "unresolved"
    proposals = []
    for option in data.get("options", []):
        risk = ConsequenceVector(**option.get("consequences", {}))
        prohibited = vector.prohibited or risk.prohibited
        proposals.append({**option, "consequences": asdict(risk),
                          "comparison_eligible": not prohibited, "exclusion": "hard rights/consent/law prohibition" if prohibited else None,
                          "legality": _state("prohibited" if risk.lawful is False else "unresolved", "applicable jurisdiction and qualified legal review required", option.get("evidence_refs", [])),
                          "consent": _state("prohibited" if risk.consent is False else "unresolved", "affected-party consent must be authenticated within its scope", option.get("evidence_refs", [])),
                          "authority": _state("unresolved", "existing Kernel gate and authenticated exact-scope authority required", []),
                          "authorized": False})
    eligible = [o for o in proposals if o["comparison_eligible"]]
    frontier = [o["id"] for o in eligible if not any(_dominates(other, o) for other in eligible if other is not o)]
    protection = protection_case(data["protection_case"]) if data.get("protection_case") else None
    obligations = {
        "evidence": _state(evidence_state, "pointer custody/completeness; factual accuracy and omissions remain unverified", refs),
        "institutional_leverage": _state("unresolved" if data.get("accepting_actor") else "not_applicable", "no acceptance proved; identified actor/process is only a proposed route", []),
        "accountability": _state("supported", "review inputs, exclusions and remedy proposal are inspectable; duties and restitution remain unresolved", [input_digest]),
        "deterrence": _state("unresolved" if data.get("deterrence_required") else "not_applicable", "no deterrent effect measured; lawful access/process and recurrence controls require review", refs),
        "victim_protection": _state("unresolved" if protection else "not_applicable", "protection review only; no professional judgment or contact performed", refs),
        "minimal_collateral_harm": _state("prohibited" if vector.prohibited else "unresolved", "hard prohibitions precede comparisons; remaining exposure and affected-party welfare need evidence", refs),
    }
    case = {"schema_version": "greg-advantage-case/0.1", "parent_input_digest": input_digest, "review_input_digest": digest(data),
            **{k: data.get(k, []) for k in ("desired_outcome", "bounded_failure", "beneficiaries", "affected_parties", "control_point", "reusable_assets", "dependencies", "strongest_counterexample", "minimum_test", "stop_conditions")},
            "existing_authority": "enclosing computation grant only; proposed effects require existing authenticated authority path",
            "consequence_vector": asdict(vector), "obligations": obligations, "protection_case": protection,
            "baseline_options": [{"id": "do_nothing", "effect": "no new action; opportunity and continuing harm remain uncertain"},
                                 {"id": "smallest_intervention", "effect": "request the minimum decisive evidence within existing data grants"}],
            "options": proposals, "conditional_scenario_frontier": frontier,
            "comparison_scope": "supplied scenario ranges only; not established lawful options, benefit or a consequential default",
            "recommendation": None, "next_step": "qualified review/evidence and existing Kernel gate before any proposed effect",
            "authority_created": False, "execution_mode": "consequence_inert"}
    package = {"schema_version": "greg-selective-disclosure/0.1", "parent_input_digest": input_digest, "review_input_digest": digest(data),
               "observations": custody, "provenance": "canonical retained-record pointers and input digest; no payload copying",
               "assumptions_ref": input_digest, "formal_result": {"proof_type": proof_type, "artifact_ref": digest(proof_artifact) if proof_artifact else None,
                                                                   "scope": "encoded computation only; retrieve under existing access controls"},
               "empirical_limitations": "WORLD_UNVERIFIED; no general truth, causality, benefit or professional competence established",
               "conflicting_evidence_refs": conflicts, "requested_remedy": data.get("requested_remedy", "qualified review only"),
               "authorized_action_record_refs": action_refs, "authorization_scope": "record custody does not create or renew authority",
               "institutional_acceptance": {"state": "UNPROVEN", "proposed_actor": data.get("accepting_actor"), "process_ref": data.get("process_ref"), "response_ref": None},
               "raw_material_disclosed": False,
               "disclosure_limit": "no original ledger payload copied; supplied proposal summaries may contain sensitive data; this is not a PII detector",
               "authority_created": False, "external_use_authorized": False}
    validate_review(case, package, input_digest=input_digest)
    return case, package


def validate_review(case, package, *, input_digest):
    """Envelope checks also apply on receipt import; a forged packet cannot claim acceptance."""
    case_fields = {"schema_version", "parent_input_digest", "review_input_digest", "desired_outcome", "bounded_failure", "beneficiaries", "affected_parties",
                   "control_point", "reusable_assets", "dependencies", "strongest_counterexample", "minimum_test", "stop_conditions",
                   "existing_authority", "consequence_vector", "obligations", "protection_case", "baseline_options", "options",
                   "conditional_scenario_frontier", "comparison_scope", "recommendation", "next_step", "authority_created", "execution_mode"}
    package_fields = {"schema_version", "parent_input_digest", "review_input_digest", "observations", "provenance", "assumptions_ref", "formal_result",
                      "empirical_limitations", "conflicting_evidence_refs", "requested_remedy", "authorized_action_record_refs",
                      "authorization_scope", "institutional_acceptance", "raw_material_disclosed", "disclosure_limit", "authority_created", "external_use_authorized"}
    if set(case) != case_fields or set(package) != package_fields:
        raise CognitionError("unknown review/disclosure field; raw evidence and acceptance cannot be added")
    if case["schema_version"] != "greg-advantage-case/0.1" or package["schema_version"] != "greg-selective-disclosure/0.1":
        raise CognitionError("unsupported review/disclosure schema")
    if case.get("parent_input_digest") != input_digest or package.get("parent_input_digest") != input_digest:
        raise CognitionError("review must bind to its receipt input")
    _refs([case["review_input_digest"], package["review_input_digest"]])
    if case["review_input_digest"] != package["review_input_digest"]:
        raise CognitionError("case and disclosure require the same proposal input")
    if set(case.get("obligations", {})) != set(OBLIGATIONS):
        raise CognitionError("all six advantage obligations must remain distinct")
    for name, assessment in case["obligations"].items():
        ScopedEvidenceState(**assessment)
        if name not in ("evidence", "accountability") and assessment["state"] == "supported":
            raise CognitionError("benefit, deterrence, welfare and institutional judgments remain unresolved")
    if case.get("authority_created") is not False or package.get("authority_created") is not False or package.get("external_use_authorized") is not False:
        raise CognitionError("proposal review cannot create disclosure or action authority")
    if case.get("recommendation") is not None or case.get("execution_mode") != "consequence_inert":
        raise CognitionError("proposal review is an inert scenario comparison")
    if case["existing_authority"] != "enclosing computation grant only; proposed effects require existing authenticated authority path" or package["authorization_scope"] != "record custody does not create or renew authority":
        raise CognitionError("review cannot enlarge the enclosing computation authority")
    if case["comparison_scope"] != "supplied scenario ranges only; not established lawful options, benefit or a consequential default":
        raise CognitionError("scenario comparison cannot establish lawful action or benefit")
    if package["disclosure_limit"] != "no original ledger payload copied; supplied proposal summaries may contain sensitive data; this is not a PII detector":
        raise CognitionError("pointer disclosure cannot claim general privacy detection")
    if package.get("raw_material_disclosed") is not False or package.get("institutional_acceptance", {}).get("state") != "UNPROVEN" or package.get("institutional_acceptance", {}).get("response_ref") is not None:
        raise CognitionError("unsupported disclosure or institutional acceptance")
    if set(package["institutional_acceptance"]) != {"state", "proposed_actor", "process_ref", "response_ref"}:
        raise CognitionError("institutional acceptance is an unproven proposed route")
    if set(package.get("formal_result", {})) != {"proof_type", "artifact_ref", "scope"}:
        raise CognitionError("formal results are pointers, not raw proof material")
    if package["formal_result"]["scope"] != "encoded computation only; retrieve under existing access controls":
        raise CognitionError("formal result cannot establish world truth through disclosure")
    if package["formal_result"]["artifact_ref"] is not None:
        _refs([package["formal_result"]["artifact_ref"]])
    for name in ("conflicting_evidence_refs", "authorized_action_record_refs"):
        _refs(package[name])
    if package["assumptions_ref"] != input_digest:
        raise CognitionError("assumptions must refer to the bounded source input")
    allowed_pointer = {"ref", "state", "scope", "record_type", "sequence", "previous_ref", "sensitivity", "raw_material_disclosed"}
    for pointer in package.get("observations", []):
        if set(pointer) != allowed_pointer or pointer["raw_material_disclosed"] is not False:
            raise CognitionError("selective disclosure contains only custody pointers")
        _refs([pointer["ref"]])
    if {o.get("id") for o in case["baseline_options"]} != {"do_nothing", "smallest_intervention"} or len(case["baseline_options"]) != 2:
        raise CognitionError("do-nothing and smallest-intervention alternatives must remain")
    global_risk = ConsequenceVector(**case["consequence_vector"])
    option_fields = {"id", "description", "consequences", "benefit_range", "benefit_unit", "resource_burden", "resource_unit", "reversibility",
                     "comparison_eligible", "exclusion", "legality", "consent", "authority", "authorized"}
    identities = set()
    for option in case.get("options", []):
        if set(option) - (option_fields | {"evidence_refs"}) or option_fields - set(option) or option["id"] in identities:
            raise CognitionError("unknown or duplicate reviewed option")
        identities.add(option["id"])
        risk = ConsequenceVector(**option["consequences"])
        for name in ("legality", "consent", "authority"):
            ScopedEvidenceState(**option[name])
        if option.get("authorized") is not False or option["legality"]["state"] == "supported" or option["consent"]["state"] == "supported":
            raise CognitionError("unsupported law, consent or authority claim")
        if option["authority"]["state"] != "unresolved":
            raise CognitionError("proposed effects retain the existing authority gate")
        if (global_risk.prohibited or risk.prohibited) and (option.get("comparison_eligible") or option["id"] in case.get("conditional_scenario_frontier", [])):
            raise CognitionError("protected-party harm cannot buy comparison eligibility")
    if any(identity not in identities for identity in case["conditional_scenario_frontier"]):
        raise CognitionError("frontier must refer to reviewed alternatives")
    retained_data(case)
    retained_data(package)


def validate_against_input(params, receipt, *, journal=None):
    """Check an imported packet against the actual signed input and current custody.

    Called by the existing evaluator, not an authority service. Source parsing,
    ledger implementation and consequence definitions are shared dependencies;
    this establishes input correspondence, not independent empirical evidence.
    """
    data = params.get("proposal_review")
    if data is None:
        if receipt.get("advantage_case") is not None or receipt.get("selective_disclosure") is not None:
            raise CognitionError("review packet absent from the actual signed input")
        return
    validate_request(data)
    case, package = receipt.get("advantage_case"), receipt.get("selective_disclosure")
    if not isinstance(case, dict) or not isinstance(package, dict):
        raise CognitionError("signed proposal review missing its result packet")
    input_ref = digest(params)
    if receipt.get("input_digest") != input_ref:
        raise CognitionError("review receipt disagrees with the actual signed input")
    validate_review(case, package, input_digest=input_ref)
    if case["review_input_digest"] != digest(data):
        raise CognitionError("review input digest mismatch")
    for name in ("desired_outcome", "bounded_failure", "beneficiaries", "affected_parties", "control_point", "reusable_assets",
                 "dependencies", "strongest_counterexample", "minimum_test", "stop_conditions"):
        if case[name] != data.get(name, []):
            raise CognitionError("review substituted a material source requirement")
    if case["consequence_vector"] != asdict(ConsequenceVector(**params.get("consequences", {}))):
        raise CognitionError("review lowered the signed consequence envelope")
    refs = data.get("evidence_refs", []) + data.get("conflicting_evidence_refs", []) + data.get("authorized_action_record_refs", [])
    refs += [r for option in data.get("options", []) for r in option.get("evidence_refs", [])]
    custody = _custody(refs, journal)
    if package["observations"] != custody:
        raise CognitionError("review custody differs from current canonical pointers")
    found = {p["ref"] for p in custody if p["state"] == "supported"}
    expected_evidence = "supported" if data.get("evidence_refs") and set(data["evidence_refs"]) <= found else "unresolved"
    if case["obligations"]["evidence"]["state"] != expected_evidence or case["obligations"]["evidence"]["evidence_refs"] != data.get("evidence_refs", []):
        raise CognitionError("review evidence state exceeds actual custody")
    expected_states = {"accountability": "supported", "institutional_leverage": "unresolved" if data.get("accepting_actor") else "not_applicable",
                       "deterrence": "unresolved" if data.get("deterrence_required") else "not_applicable",
                       "victim_protection": "unresolved" if data.get("protection_case") else "not_applicable",
                       "minimal_collateral_harm": "prohibited" if ConsequenceVector(**params.get("consequences", {})).prohibited else "unresolved"}
    if any(case["obligations"][name]["state"] != expected for name, expected in expected_states.items()):
        raise CognitionError("review changed a material obligation disposition")
    scopes = {
        "evidence": "pointer custody/completeness; factual accuracy and omissions remain unverified",
        "institutional_leverage": "no acceptance proved; identified actor/process is only a proposed route",
        "accountability": "review inputs, exclusions and remedy proposal are inspectable; duties and restitution remain unresolved",
        "deterrence": "no deterrent effect measured; lawful access/process and recurrence controls require review",
        "victim_protection": "protection review only; no professional judgment or contact performed",
        "minimal_collateral_harm": "hard prohibitions precede comparisons; remaining exposure and affected-party welfare need evidence",
    }
    for name, scope in scopes.items():
        expected_refs = [input_ref] if name == "accountability" else [] if name == "institutional_leverage" else data.get("evidence_refs", [])
        if case["obligations"][name] != _state(expected_evidence if name == "evidence" else expected_states[name], scope, expected_refs):
            raise CognitionError("review enlarged a scoped obligation claim")
    original = {o["id"]: o for o in data.get("options", [])}
    if set(original) != {o["id"] for o in case["options"]}:
        raise CognitionError("review omitted or invented an intervention")
    global_risk = ConsequenceVector(**params.get("consequences", {}))
    for option in case["options"]:
        source = original[option["id"]]
        if any(option[name] != source[name] for name in ("description", "benefit_range", "benefit_unit", "resource_burden", "resource_unit", "reversibility")):
            raise CognitionError("review substituted scenario inputs")
        risk = ConsequenceVector(**source.get("consequences", {}))
        if option["consequences"] != asdict(risk) or option["comparison_eligible"] != (not (risk.prohibited or global_risk.prohibited)):
            raise CognitionError("review dropped a hard condition")
    eligible = [o for o in case["options"] if o["comparison_eligible"]]
    expected_frontier = [o["id"] for o in eligible if not any(_dominates(other, o) for other in eligible if other is not o)]
    if case["conditional_scenario_frontier"] != expected_frontier:
        raise CognitionError("review frontier differs from its bounded source constraints")
    if case["protection_case"] != (protection_case(data["protection_case"]) if data.get("protection_case") else None):
        raise CognitionError("review omitted or changed material protection conditions")
    acceptance = package["institutional_acceptance"]
    if acceptance["proposed_actor"] != data.get("accepting_actor") or acceptance["process_ref"] != data.get("process_ref"):
        raise CognitionError("review invented an institutional actor or process")
    if package["conflicting_evidence_refs"] != data.get("conflicting_evidence_refs", []) or package["authorized_action_record_refs"] != data.get("authorized_action_record_refs", []):
        raise CognitionError("review substituted conflicting evidence or action records")
    if package["requested_remedy"] != data.get("requested_remedy", "qualified review only"):
        raise CognitionError("review substituted the requested remedy")
