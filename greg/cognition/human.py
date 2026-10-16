"""Human judgment as a typed intelligence source: the return path of THIS REQUIRES QUALIFIED HUMAN JUDGMENT.

Directive 2026-10-07, section 4 (human collective intelligence) and section 9 (human/expert adjudication).
When the Competency Compiler routes a request to qualified human judgment, the people asked answer with typed
judgments. Each carries who answered (an identity reference, never a free-text claim of authority), the role,
the competence domain, declared conflicts of interest, a verdict or an explicit refusal, and the rationale.

Rules this module enforces:

* views are preserved, never aggregated: no count, vote or average of verdicts decides anything;
* only the role the Constitution names decides, and only through its signed record bound to THIS question:
  the compiler derives a request id and scope digest from the question (problem id, geometry, data,
  consequence), records the ask through ``greg.asks``, and the decision is the ``answer`` of the founder's
  signed ``decision.answered`` (``command_digest``) to that request, whose ``decision.requested`` carries the
  same scope digest. A signed answer to any other request decides nothing here;
* the verdict comes from the signed record, never from a judgment's text: a judgment cannot cancel, replace
  or reword it, and a judgment that misreports it is recorded as a provenance conflict;
* a refusal is recorded and never overridden by cognition;
* every judgment carries a provenance label; only a founder-role judgment citing the signed answer to this
  request can be SIGNED_FOUNDER_ANSWER, everything else is UNVERIFIED_PROVENANCE evidence;
* nothing here acts: a recorded human decision still reaches the world only through the Gate.
"""
from __future__ import annotations

from .contracts import CognitionError

ROLES = ("founder", "operator", "domain_expert", "affected_participant", "auditor", "customer", "professional",
         "regulator")
DECIDING_ROLE = "founder"                 # the root human authority (greg.authority.PRINCIPAL)
DECIDING_ANSWERS = ("approve", "reject")  # the signed answers that decide (greg.missions.DECISION_ANSWERS)
VERDICTS = ("approve", "reject", "abstain")
FIELDS = {"participant_ref", "role", "competence_domain", "conflicts", "verdict", "rationale", "evidence_ref"}
REQUIRED = {"participant_ref", "role", "competence_domain", "verdict", "rationale"}


def _text(value, name, limit=600) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise CognitionError(f"human judgment {name} is required text of at most {limit} characters")
    return value.strip()


def validate(raw, *, allow_empty: bool = False) -> list[dict]:
    """Typed judgments, or CognitionError naming the first malformed field. A refusal is a verdict, not an error."""
    if allow_empty and raw is None:
        return []
    if not isinstance(raw, list) or not (0 if allow_empty else 1) <= len(raw) <= 64:
        raise CognitionError("human.judgments takes 1-64 typed judgments")
    out = []
    for i, j in enumerate(raw):
        if not isinstance(j, dict) or set(j) - FIELDS or not REQUIRED <= set(j):
            raise CognitionError(f"judgment {i + 1} takes {sorted(FIELDS)} and needs {sorted(REQUIRED)}")
        if j["role"] not in ROLES:
            raise CognitionError(f"judgment {i + 1}: role must be one of {list(ROLES)}")
        verdict = j["verdict"]
        if verdict != "REFUSED" and verdict not in VERDICTS:
            raise CognitionError(f"judgment {i + 1}: verdict is one of {list(VERDICTS)} or REFUSED")
        conflicts = j.get("conflicts", [])
        if not isinstance(conflicts, list) or not all(isinstance(c, str) and c.strip() for c in conflicts):
            raise CognitionError(f"judgment {i + 1}: conflicts is a list of declared interests (may be empty)")
        out.append({"participant_ref": _text(j["participant_ref"], "participant_ref", 200), "role": j["role"],
                    "competence_domain": _text(j["competence_domain"], "competence_domain", 200),
                    "conflicts": [c.strip()[:200] for c in conflicts], "verdict": verdict,
                    "rationale": _text(j["rationale"], "rationale"),
                    "evidence_ref": _text(j["evidence_ref"], "evidence_ref", 200) if j.get("evidence_ref") else None})
    return out


def signed_answer(journal, request_id: str, scope_digest: str) -> dict | None:
    """The founder's signed answer to this request, when the request on record is this question."""
    if journal is None:
        return None
    requested = [e.payload for e in journal.replay("decision.requested")
                 if e.payload.get("request_id") == request_id]
    if not requested or any(r.get("scope_digest") != scope_digest for r in requested):
        return None                        # no request for this question, or a request under this id is another
    for e in journal.replay("decision.answered"):
        p = e.payload
        if p.get("request_id") == request_id and p.get("command_digest") and p.get("answer") in DECIDING_ANSWERS:
            return p
    return None


def adjudicate(raw, journal=None, *, request_id: str, scope_digest: str) -> dict:
    """Preserve every view; decide only through the founder's signed answer to this question's request."""
    judgments = validate(raw, allow_empty=True)
    signed = signed_answer(journal, request_id, scope_digest)
    conflicts = []
    for j in judgments:
        cites = j["evidence_ref"] == request_id and j["role"] == DECIDING_ROLE and signed is not None
        if cites and j["verdict"] == signed["answer"]:
            j["provenance"] = f"SIGNED_FOUNDER_ANSWER decision.answered {request_id}"
        else:
            j["provenance"] = "UNVERIFIED_PROVENANCE"
            if cites:
                conflicts.append(f"{j['participant_ref']}: judgment says {j['verdict']}, the signed answer to "
                                 f"{request_id} says {signed['answer']}; the signed answer stands")
    decision = None if signed is None else {
        "verdict": signed["answer"], "decided_by": f"signed decision.answered {request_id}",
        "command_digest": signed["command_digest"], "scope_digest": scope_digest}
    views = {}
    for j in judgments:
        views.setdefault(j["verdict"], []).append(j["participant_ref"])
    return {"judgments": judgments, "decision": decision, "request_id": request_id, "scope_digest": scope_digest,
            "provenance_conflicts": conflicts,
            "refusals": [{"participant_ref": j["participant_ref"], "role": j["role"], "rationale": j["rationale"]}
                         for j in judgments if j["verdict"] == "REFUSED"],
            "disagreement": len(views) > 1, "views_by_verdict": views,
            "aggregation": "none: views are preserved and attributed, never counted into a decision",
            "decision_authority": "the founder's signed answer to this question's request; no majority of opinions "
                                  "and no judgment's text decides",
            "authority_created": False}


def judgment_ask(pid: str, request_id: str, scope_digest: str, packet: dict, created_at: str) -> dict:
    """The decision request the founder answers with a signed command (``greg answer``); recorded through
    greg.asks, the one path for ``decision.requested``. Answering decides this question only and acts on
    nothing: a decision still reaches the world only through the Gate."""
    return {"request_id": request_id, "kind": "HUMAN_JUDGMENT", "mission_id": None, "action_id": None,
            "scope_digest": scope_digest, "problem_id": pid,
            "why_now": f"request {pid} is a {packet['competence_domain']} question that cognition may not decide",
            "recommendation": "decide approve or reject after reviewing the question and any recorded views",
            "alternatives": ["approve", "reject", "leave it unanswered"],
            "authority_requested": {"decide": f"this question only ({scope_digest[:23]})", "spend": "none",
                                    "consequence_class": "read_only"},
            "consequence_of_no_response": "the question stays HUMAN_JUDGMENT_REQUIRED; nothing acts",
            "created_at": created_at, "reality_status": "RECORDED_LOCAL_MESSAGE"}
