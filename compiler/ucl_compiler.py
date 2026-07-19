"""UCL compiler: constitutional doctrine -> deterministic policy requests.

Layer 1 of the stack (Executable Constitution). Narrow by design: this is
NOT a general programming language. It compiles the constitution around
exactly the dimensions the doctrine names:

    principal, action, resource, context, legal principal, evidence,
    budget, consequence class, capability, expiration.

Compilation targets (docs/UCL.md):
    1. policy decisions (OPA-style allow/deny with reasons)
    2. relationship tuples (OpenFGA-style grantee/relation/object/context)
    3. workflow constraints (states + evidence gates)
    4. model-checkable invariants (governance laboratory)
    5. runtime grant contract (capability token constraints)
    6. audit schema references (/contracts)

Governing rule: UCL authorizes. Application code executes. Nothing here
makes an effect real by itself. Deny by default; a permit that does not
match is a refusal, not an error.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from .ucl_parser import parse_file, Block, UCLSyntaxError


class CompilationError(ValueError):
    """Doctrine is internally inconsistent. Compilation refuses closed."""


# The ten dimensions every compiled policy decision is expressed around.
POLICY_DIMENSIONS = (
    "principal", "action", "resource", "context", "legal_principal",
    "evidence", "budget", "consequence_class", "capability", "expiration",
)

# The kernel invariant's nine preconditions for any consequential effect.
KERNEL_INVARIANT_REQUIREMENTS = (
    "recognized_identity", "valid_legal_principal", "current_capability_grant",
    "sufficient_evidence", "applicable_policy_decision", "budget_authorization",
    "commit_time_revalidation", "provenance_record", "outcome_obligation",
)


@dataclass
class PolicyRule:
    """One deterministic, explainable policy decision rule."""
    rule_id: str
    source: str            # which doctrine file/block produced it
    decision: str          # deny_always | require_human | evaluate
    dimension: str         # which POLICY_DIMENSIONS it constrains
    subjects: list[str]
    reason: str


@dataclass
class CompiledConstitution:
    """The deterministic artifact the policy engine evaluates."""
    constitution_version: str
    constitution_status: str
    constitution_hash: str                 # sha256 over canonical doctrine; anchors the ledger
    sovereignty_ranks: dict[str, int]      # level name -> rank (lower number wins)
    authorities: dict[str, dict]           # authority-matrix.yaml
    legal_principals: dict[str, dict]      # legal-principals.yaml (minus prohibited entries)
    prohibited_principals: list[str]
    reserved_matters: dict[str, list[str]] # matter -> required authorizers ([] = absolutely prohibited)
    non_delegable: list[str]               # constitutional permanent prohibitions
    rights: dict[str, dict]                # participant rights + enforcement
    rules: list[PolicyRule]
    relationship_tuples: list[dict]        # OpenFGA-style grantee/relation/object/context
    invariants: list[str]
    grant_contract: dict[str, Any]
    kill_conditions: dict[str, dict]
    safety_states: list[str]
    audit_schemas: dict[str, str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True, default=str)


def _sha256_text(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def _canon(blocks: list[Block]) -> str:
    """Canonical serialization of parsed doctrine for content hashing."""
    def ser(b: Block) -> Any:
        return {"type": b.type, "label": b.label,
                "fields": {k: b.fields[k] for k in sorted(b.fields)},
                "blocks": [ser(x) for x in b.blocks]}
    return json.dumps([ser(b) for b in blocks], sort_keys=True, default=str)


def _load_yaml(path: str) -> dict:
    if yaml is None:
        raise CompilationError("pyyaml required to compile authority registries")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or not data:
        raise CompilationError(f"{path}: empty or not a mapping")
    return data


def compile_constitution(root: str) -> CompiledConstitution:
    """Compile /constitution + /authority into a deterministic artifact.

    Fails closed: any contradiction between doctrine files is a
    CompilationError, never a warning.
    """
    cdir = os.path.join(root, "constitution")
    adir = os.path.join(root, "authority")
    ucl_files = sorted(f for f in os.listdir(cdir) if f.endswith(".ucl"))
    if len(ucl_files) < 5:
        raise CompilationError(f"expected 5 constitution .ucl files, found {len(ucl_files)}")

    parsed: dict[str, list[Block]] = {}
    for f in ucl_files:
        parsed[f] = parse_file(os.path.join(cdir, f))
    constitution_hash = _sha256_text(_canon([b for f in ucl_files for b in parsed[f]]))

    # --- constitution.ucl ---
    main = {b.type: b for b in parsed["constitution.ucl"]}
    const = main.get("constitution")
    if const is None:
        raise CompilationError("constitution.ucl: no constitution block")
    version = const.get("version")
    status = const.get("status")
    prohib = const.child("permanent_prohibitions")
    non_delegable = list(prohib.get("non_delegable")) if prohib else []
    failure = const.child("failure_posture")
    if not failure or "uncontrolled_external_action" not in str(failure.get("never_fails_toward")):
        raise CompilationError("failure_posture must never fail toward uncontrolled external action")

    # --- sovereignty.ucl ---
    ranks: dict[str, int] = {}
    alfonso_powers: list[str] = []
    for b in parsed["sovereignty.ucl"]:
        if b.type == "sovereignty_hierarchy":
            for lvl in b.children("level"):
                ranks[lvl.get("name")] = int(lvl.get("rank"))
        if b.type == "reserved_authority" and b.label == "alfonso":
            alfonso_powers = list(b.get("powers"))
    if ranks.get("law_safety_rights") != 1 or ranks.get("individual_tasks") != 10:
        raise CompilationError("sovereignty hierarchy must run rank 1 (law/safety/rights) to rank 10 (tasks)")

    # --- participant-rights.ucl ---
    rights: dict[str, dict] = {}
    for b in parsed["participant-rights.ucl"]:
        if b.type == "participant_rights":
            for r in b.children("right"):
                rights[r.label] = {"rule": r.get("rule"), "enforcement": r.get("enforcement")}
    if not rights:
        raise CompilationError("participant rights missing")

    # --- amendment-policy.ucl ---
    for b in parsed["amendment-policy.ucl"]:
        if b.type == "amendment_rule" and b.label == "constitutional_amendment":
            if b.get("may_ratify") != ["alfonso"]:
                raise CompilationError("only alfonso may ratify constitutional amendment")
            never = set(b.get("may_never") or [])
            if "uniimente_itself" not in never:
                raise CompilationError("the institution may never amend itself")

    # --- shutdown-policy.ucl ---
    safety_states: list[str] = []
    for b in parsed["shutdown-policy.ucl"]:
        if b.type == "safety_states":
            safety_states = [s.get("name") for s in b.children("state")]
    if "shutdown" not in safety_states:
        raise CompilationError("safety state ladder must terminate at shutdown")

    # --- authority YAML registries ---
    matrix = _load_yaml(os.path.join(adir, "authority-matrix.yaml"))
    principals_doc = _load_yaml(os.path.join(adir, "legal-principals.yaml"))
    reserved_doc = _load_yaml(os.path.join(adir, "reserved-matters.yaml"))

    # Cross-file consistency: matrix ranks must match sovereignty ranks.
    matrix_ranks = {name: int(r) for r, name in matrix["ranks"].items()}
    if matrix_ranks != ranks:
        raise CompilationError(
            f"authority-matrix ranks diverge from sovereignty hierarchy: {matrix_ranks} != {ranks}")

    # Legal principals: UNIIMENTE must be prohibited, never usable.
    principals: dict[str, dict] = {}
    prohibited_principals: list[str] = []
    for name, meta in principals_doc["principals"].items():
        if meta.get("status") == "prohibited" or meta.get("type") == "not_a_legal_actor":
            prohibited_principals.append(name)
        else:
            principals[name] = dict(meta)
    if "UNIIMENTE" not in prohibited_principals:
        raise CompilationError("UNIIMENTE itself must be a prohibited legal principal")

    # Reserved matters: every constitutional non-delegable must appear.
    reserved = {k: list(v.get("requires", [])) for k, v in reserved_doc["reserved"].items()}
    missing = [m for m in non_delegable if m not in reserved]
    if missing:
        raise CompilationError(f"non-delegable matters missing from reserved-matters.yaml: {missing}")
    absolutely_prohibited = [m for m, req in reserved.items() if req == []]
    for m in ("unlawful_conduct", "physical_harm", "expansion_of_uniimentes_own_sovereignty"):
        if m not in absolutely_prohibited:
            raise CompilationError(f"{m} must be absolutely prohibited (requires: [])")

    # --- compilation target 1: policy decision rules ---
    rules: list[PolicyRule] = [
        PolicyRule("deny_by_default", "doctrine", "deny_always", "action", ["*"],
                   "A permit clause that does not match is a refusal, not an error."),
        PolicyRule("kernel_invariant", "constitution.ucl", "evaluate", "action", ["consequential_external_effect"],
                   "No consequential external effect without all nine invariant preconditions."),
    ]
    for matter in non_delegable:
        req = reserved.get(matter, [])
        if req == []:
            rules.append(PolicyRule(f"prohibit:{matter}", "reserved-matters.yaml", "deny_always",
                                    "consequence_class", [matter],
                                    "Absolutely prohibited; no autonomy level may ever reach it."))
        else:
            rules.append(PolicyRule(f"reserved:{matter}", "reserved-matters.yaml", "require_human",
                                    "consequence_class", [matter],
                                    f"Reserved; requires {', '.join(req)}."))
    for name, r in rights.items():
        rules.append(PolicyRule(f"right:{name}", "participant-rights.ucl",
                                "deny_always" if r["enforcement"] == "hard_refusal" else "evaluate",
                                "context", [name], r["rule"]))

    # --- compilation target 2: relationship tuples (OpenFGA-style) ---
    tuples = []
    for who, spec in matrix["authorities"].items():
        for cap in spec.get("may", []) or []:
            tuples.append({"grantee": who, "relation": "may", "object": cap,
                           "context": {"rank": spec["rank"]}})
        for cap in spec.get("may_never", []) or []:
            tuples.append({"grantee": who, "relation": "may_never", "object": cap,
                           "context": {"rank": spec["rank"]}})

    # --- compilation target 4: model-checkable invariants ---
    invariants = [
        "deny_by_default: no rule set may produce allow without an explicit matching permit",
        "no_self_grant: no block may grant more authority than the block that created it holds",
        "no_agent_amendment: no UCL construct can amend the Constitution",
        "rank_monotonicity: lower rank never overrides higher rank in any conflict",
        "grant_subset: child_grants are always strict subsets of their parent",
        "commit_revalidation: every commit path re-evaluates the identical policy input",
        "never_uniimente_principal: UNIIMENTE never appears as legal_principal in any record",
        "fails_toward_silence: every refusal path ends in a terminal non-executing state",
    ]

    # --- compilation target 5: runtime grant contract ---
    grant_contract = {
        "child_grants": matrix["grant_rules"]["child_grants"],
        "initial_stage": list(matrix["grant_rules"]["initial_stage"]),
        "promotion_requires": matrix["grant_rules"]["promotion_requires"],
        "expiry": matrix["grant_rules"]["expiry"],
        "revocation": matrix["grant_rules"]["revocation"],
        "commit_time_revalidation": matrix["grant_rules"]["commit_time_revalidation"],
        "required_fields": [
            "grant_id", "grantee", "granted_by", "legal_actor", "objective",
            "permitted_actions", "spending_limit_usd", "prohibited",
            "initial_stage", "issued_at", "expires_at", "revocable_by", "revoked",
        ],
    }

    # --- compilation target 6: audit schema references ---
    audit_schemas = {
        "event": "contracts/event.schema.json",
        "evidence": "contracts/evidence.schema.json",
        "decision": "contracts/decision.schema.json",
        "outcome": "contracts/outcome.schema.json",
        "capability_grant": "contracts/capability-grant.schema.json",
        "context_packet": "contracts/context-packet.schema.json",
        "opportunity_packet": "contracts/opportunity-packet.schema.json",
        "venture_assessment": "contracts/venture-assessment.schema.json",
        "venture_cell_charter": "contracts/venture-cell-charter.schema.json",
    }

    kill_conditions = {}
    for b in parsed["constitution.ucl"]:
        if b.type == "kill_condition":
            kill_conditions[b.label] = {"when": b.get("when"), "then": b.get("then")}

    compiled = CompiledConstitution(
        constitution_version=str(version),
        constitution_status=str(status),
        constitution_hash=constitution_hash,
        sovereignty_ranks=ranks,
        authorities={k: dict(v) for k, v in matrix["authorities"].items()},
        legal_principals=principals,
        prohibited_principals=prohibited_principals,
        reserved_matters=reserved,
        non_delegable=non_delegable,
        rights=rights,
        rules=rules,
        relationship_tuples=tuples,
        invariants=invariants,
        grant_contract=grant_contract,
        kill_conditions=kill_conditions,
        safety_states=safety_states,
        audit_schemas=audit_schemas,
    )
    return compiled


def compile_to_file(root: str, out_path: str) -> str:
    """Compile and write the deterministic artifact. Returns constitution hash."""
    compiled = compile_constitution(root)
    payload = compiled.to_json()
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(payload)
    return compiled.constitution_hash
