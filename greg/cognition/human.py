"""Human judgment as a typed intelligence source: the return path of THIS REQUIRES QUALIFIED HUMAN JUDGMENT.

Directive 2026-10-07, section 4 (human collective intelligence) and section 9 (human/expert adjudication).
When the Competency Compiler routes a request to qualified human judgment, the people asked answer with typed
judgments. Each carries who answered (an identity reference, never a free-text claim of authority), the role,
the competence domain, declared conflicts of interest, a verdict or an explicit refusal, and the rationale.

Rules this module enforces:

* views are preserved, never aggregated: no count, vote or average of verdicts decides anything;
* only the role the Constitution names decides, and only through its signed record: a founder judgment is
  decisive when, and only when, it cites a ``decision.answered`` event in the canonical journal (signed
  founder command, ``command_digest``) whose answer is the same verdict;
* a refusal is recorded and never overridden by cognition;
* a judgment whose provenance cannot be shown stays evidence, labelled UNVERIFIED_PROVENANCE;
* nothing here acts: a recorded human decision still reaches the world only through the Gate.
"""
from __future__ import annotations

from .contracts import CognitionError

ROLES = ("founder", "operator", "domain_expert", "affected_participant", "auditor", "customer", "professional",
         "regulator")
DECIDING_ROLE = "founder"                 # the root human authority (greg.authority.PRINCIPAL)
VERDICTS = ("approve", "reject", "abstain")
FIELDS = {"participant_ref", "role", "competence_domain", "conflicts", "verdict", "rationale", "evidence_ref"}
REQUIRED = {"participant_ref", "role", "competence_domain", "verdict", "rationale"}


def _text(value, name, limit=600) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise CognitionError(f"human judgment {name} is required text of at most {limit} characters")
    return value.strip()


def validate(raw) -> list[dict]:
    """Typed judgments, or CognitionError naming the first malformed field. A refusal is a verdict, not an error."""
    if not isinstance(raw, list) or not 1 <= len(raw) <= 64:
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


def _signed_answers(journal) -> dict:
    if journal is None:
        return {}
    return {e.payload["request_id"]: e.payload for e in journal.replay("decision.answered")
            if e.payload.get("command_digest")}


def adjudicate(raw, journal=None) -> dict:
    """Preserve every view; decide only through the deciding role's signed answer."""
    judgments = validate(raw)
    signed = _signed_answers(journal)
    decision, conflicts = None, []
    for j in judgments:
        record = signed.get(j["evidence_ref"]) if j["evidence_ref"] else None
        if record is None:
            j["provenance"] = "UNVERIFIED_PROVENANCE"
            continue
        j["provenance"] = f"signed decision.answered {j['evidence_ref']}"
        if j["role"] != DECIDING_ROLE:
            continue                       # a signed record of someone else's answer still decides nothing here
        if record.get("answer") != j["verdict"]:
            conflicts.append(f"{j['participant_ref']}: judgment says {j['verdict']}, the signed answer says "
                             f"{record.get('answer')}")
            continue
        if decision is not None and decision["verdict"] != j["verdict"]:
            conflicts.append(f"two signed founder answers disagree ({decision['verdict']} vs {j['verdict']})")
            decision = None
            break
        decision = {"verdict": j["verdict"], "decided_by": j["provenance"], "participant_ref": j["participant_ref"]}
    views = {}
    for j in judgments:
        views.setdefault(j["verdict"], []).append(j["participant_ref"])
    return {"judgments": judgments, "decision": None if conflicts else decision,
            "provenance_conflicts": conflicts,
            "refusals": [{"participant_ref": j["participant_ref"], "role": j["role"], "rationale": j["rationale"]}
                         for j in judgments if j["verdict"] == "REFUSED"],
            "disagreement": len(views) > 1, "views_by_verdict": views,
            "aggregation": "none: views are preserved and attributed, never counted into a decision",
            "decision_authority": "the founder's signed answer; no majority of opinions decides",
            "authority_created": False}
