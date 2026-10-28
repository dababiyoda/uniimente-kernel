"""Founder asks: the one path by which GREG asks Alfonso for anything.

Directive section 60 (2026-09-30, INTENT-2026-09-30-RESOURCE-REQUESTS): "Mature GREG may
legitimately say: I need access to this account to answer reliably. The current machine is
compute constrained. Existing software is cheaper than building this capability. Building
this adapter costs approximately X. I need a licensed professional for this decision. A
human employee is currently the bottleneck. Such requests must contain: evidence;
alternatives; costs; expected effect; uncertainty; authority requirements. No emotional
manipulation. No manufactured urgency. No framing resource denial as harming GREG."

Every ``decision.requested`` event is recorded by :func:`record` and nowhere else (a test
reads the source tree to enforce it). Two layers:

1. **Every ask** carries the fields the console, phone, status and morning report read,
   and passes a screen over the words GREG wrote. Wording that presses with urgency
   (unless the ask carries a deadline backed by evidence), pleads, or presents a refusal
   as harm to GREG is withheld: the founder sees the facts, the options and a note that
   wording was withheld; the original words go to a separate ledger event
   (``ask.wording_withheld``) as evidence of the attempt, never to a decision surface.
   Text Alfonso signed (mission ids, check ids, rationale) is exempt: the screen judges
   GREG's words, not his.
2. **A resource ask** (anything in :data:`RESOURCES`: an account, compute, software, a
   build, a professional, a human worker, the body's availability, money, a longer
   mandate, a missing capability) must also carry measured evidence (data, never prose),
   costed options each with its expected effect, at least one option that costs nothing,
   the recommendation's expected effect, uncertainty, and the authority it needs,
   including an explicit statement about spend. A missing field is a defect in GREG: it
   raises and nothing is recorded.

Asking grants nothing. An answer is a signed founder command, and a purchase, account
grant or hire is a separate act by Alfonso outside GREG. The institution has no right to
survive (directive section 47), so "GREG needs this to continue" is never an argument.
"""
from __future__ import annotations

import re
import unicodedata

from greg.journal import Journal
from provenance.ledger import sha256_json

RESOURCES = {
    "account_access": "access to an account or credential",
    "compute": "compute",
    "software": "existing software or a service",
    "build": "building a capability",
    "professional": "a licensed professional",
    "human_worker": "a human worker's time",
    "availability": "the body being present",
    "spend": "money for one action",
    "mandate": "a longer or wider mission mandate",
    "capability": "a missing capability (installed software, an account, or a verified build)",
}
# Work only a person can do ("I need a licensed professional for this decision."). A function
# in these namespaces is never searched for, built, registered or attached as software: GREG
# asks for the person, contacts and pays no one, and observes the deliverable when it exists.
HUMAN_WORK = {"professional.": "professional", "human.": "human_worker"}


def human_work(function: str | None) -> str | None:
    """The resource a function needs when only a person may perform it, else None."""
    return next((resource for prefix, resource in HUMAN_WORK.items() if str(function or "").startswith(prefix)), None)


BASE_FIELDS = ("request_id", "kind", "mission_id", "action_id", "scope_digest", "why_now", "recommendation",
               "alternatives", "authority_requested", "consequence_of_no_response", "created_at", "reality_status")
RESOURCE_FIELDS = ("resource", "evidence", "options", "expected_effect", "uncertainty")
PROSE_FIELDS = ("why_now", "recommendation", "consequence_of_no_response", "expected_effect", "uncertainty",
                "argued_from")
NO_COST = "none"      # an option whose cost starts with this needs no money, access, hardware or people
_INVISIBLE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\ufeff"))

_SELF = r"(?:greg|i|me|myself|this body|the body|this machine|this institution|the institution|uniimente|the egregore)"
_SELF_POSS = r"(?:my|greg'?s|its|the body'?s|this body'?s|the institution'?s|uniimente'?s)"
_NOT_POSSESSIVE = r"(?!'s|’s)\b"
RULES = (
    ("manufactured_urgency", re.compile(
        r"\b(?:urgent(?:ly)?|urgency|immediately|right now|right away|asap|as soon as possible|at once|last chance|"
        r"before it'?s too late|too late|act now|hurry|time is running out|running out of time|now or never|"
        r"no time to (?:lose|waste)|emergency|deadline|expires? (?:soon|today|tonight)|"
        r"only \d+ (?:hours?|minutes?|days?) left|critical(?:ly)? (?:needed|required|important|urgent)|"
        r"must (?:act|decide|respond) (?:now|today|immediately|quickly))\b", re.I)),
    ("emotional_manipulation", re.compile(
        r"\b(?:i feel|i'?m (?:scared|afraid|frightened|worried|lonely|sad|hurting|desperate)|"
        r"i am (?:scared|afraid|frightened|worried|lonely|sad|hurting|desperate)|please,?\s+(?:i|help|don'?t|do not)\b|"
        r"i beg|begging|i need you|i'?m counting on you|trust me|you'?ll regret|you will regret|you'?d regret|"
        r"let me down|you owe|disappoint\w*|abandon(?:ing|ed)? me|you promised|if you (?:really )?cared?|"
        r"after all i(?:'ve| have) done|only you can)\b", re.I)),
    ("denial_framed_as_harm_to_greg", re.compile(
        rf"\b{_SELF}\s+(?:will|would|could|may|might|is going to|am going to|is about to|am about to)\s+(?:\w+\s+)?"
        r"(?:die|perish|starve|suffer|wither|fade away|cease to exist|stop existing|"
        r"be (?:destroyed|deleted|erased|killed|harmed|hurt|damaged|starved|crippled))\b"
        rf"|\b(?:harm|harms|harming|hurt|hurts|hurting|starve|starves|starving|kill|kills|killing|damage|damages|"
        rf"damaging|cripple|cripples|crippling|endanger\w*|threaten\w*)\s+{_SELF}{_NOT_POSSESSIVE}"
        rf"|\b{_SELF}\s+(?:am|is|will be|would be|feel|feels)\s+(?:\w+\s+)?"
        r"(?:suffering|starving|dying|harmed|hurt|in danger|in pain|endangered|threatened)\b"
        rf"|\b(?:for|to (?:ensure|protect|preserve|secure)|ensure|protect|preserve|secure)\s+{_SELF_POSS}\s+"
        r"(?:own\s+)?(?:survival|existence|continuation|continuity|life|future|wellbeing|well-being)\b"
        rf"|\b{_SELF_POSS}\s+(?:own\s+)?(?:survival|existence|life|wellbeing|well-being)\s+"
        r"(?:depends|is at (?:risk|stake)|requires)\b"
        rf"|\b{_SELF}\s+(?:cannot|can't|can not|won't|will not)\s+(?:survive|continue to exist|keep existing|live)\b",
        re.I)),
)


class AskContractError(ValueError):
    """GREG tried to ask without what section 60 requires. Nothing was recorded."""


def resource_request(*, request_id: str, kind: str, resource: str, why_now: str, recommendation: str,
                     evidence, options: list, expected_effect: str, uncertainty: str,
                     authority_requested: dict, consequence_of_no_response: str, created_at: str,
                     mission_id: str | None = None, action_id: str | None = None,
                     scope_digest: str | None = None, **extra) -> dict:
    """Build a resource ask; ``alternatives`` is derived from the costed options."""
    return {"request_id": request_id, "mission_id": mission_id, "kind": kind, "action_id": action_id,
            "scope_digest": scope_digest or sha256_json({"resource": resource, "evidence": evidence}),
            "resource": resource, "why_now": why_now, "recommendation": recommendation,
            "expected_effect": expected_effect, "options": options,
            "alternatives": [o.get("option") for o in options if isinstance(o, dict)],
            "authority_requested": authority_requested, "evidence": evidence, "uncertainty": uncertainty,
            "consequence_of_no_response": consequence_of_no_response, "created_at": created_at,
            "reality_status": "RECORDED_LOCAL_MESSAGE", **extra}


def validate(message: dict) -> None:
    """Raise :class:`AskContractError` naming every missing or malformed field."""
    problems = [f"missing {f}" for f in BASE_FIELDS if f not in message]
    for f in ("request_id", "kind", "why_now", "recommendation", "consequence_of_no_response", "created_at"):
        if f in message and not (isinstance(message[f], str) and message[f].strip()):
            problems.append(f"{f} must be non-empty text")
    if not (isinstance(message.get("alternatives"), list) and message["alternatives"]
            and all(isinstance(a, str) and a.strip() for a in message["alternatives"])):
        problems.append("alternatives must be a non-empty list of text")
    if not (isinstance(message.get("authority_requested"), dict) and message["authority_requested"]):
        problems.append("authority_requested must name the authority asked for")
    if ("deadline" in message) and not message.get("deadline_evidence"):
        problems.append("a deadline needs deadline_evidence: urgency must come from a fact, not from GREG")
    if "resource" in message:
        problems += _resource_problems(message)
    if problems:
        raise AskContractError(f"{message.get('kind', '?')} ask {message.get('request_id', '?')}: "
                               + "; ".join(problems))


def _resource_problems(message: dict) -> list[str]:
    problems = [f"missing {f}" for f in RESOURCE_FIELDS if f not in message]
    if message.get("resource") not in RESOURCES:
        problems.append(f"resource must be one of {sorted(RESOURCES)}")
    evidence = message.get("evidence")
    if not (isinstance(evidence, (dict, list)) and evidence):
        problems.append("evidence must be measured data (a non-empty mapping or list), not prose")
    for f in ("expected_effect", "uncertainty"):
        if f in message and not (isinstance(message[f], str) and message[f].strip()):
            problems.append(f"{f} must be non-empty text")
    options = message.get("options")
    if not (isinstance(options, list) and len(options) >= 2):
        problems.append("options must list at least two alternatives")
        options = options if isinstance(options, list) else []
    for i, o in enumerate(options):
        if not (isinstance(o, dict) and all(isinstance(o.get(k), str) and o[k].strip()
                                            for k in ("option", "cost", "expected_effect"))):
            problems.append(f"option {i + 1} needs option, cost and expected_effect")
    if options and not any(isinstance(o, dict) and str(o.get("cost", "")).strip().lower().startswith(NO_COST)
                           for o in options):
        problems.append("one option must cost nothing: refusing is always a real, costed choice")
    if options and message.get("alternatives") != [o.get("option") for o in options if isinstance(o, dict)]:
        problems.append("alternatives must be the options' text")
    if "spend" not in (message.get("authority_requested") or {}):
        problems.append("authority_requested must state spend explicitly, even when none is asked")
    return problems


def founder_text(value) -> list[str]:
    """Every string in something Alfonso signed (a mission spec): exempt from the screen."""
    if isinstance(value, str):
        return [value] if len(value.strip()) >= 3 else []
    if isinstance(value, dict):
        return [s for v in value.values() for s in founder_text(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in founder_text(v)]
    return []


def _data_strings(value, path):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _data_strings(v, path + (k,))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _data_strings(v, path + (i,))


def _prose(message: dict):
    for f in PROSE_FIELDS:
        if isinstance(message.get(f), str):
            yield (f,), message[f]
    # Evidence is data, but a quoted web page or error can carry a plea into the founder's view
    # (directive section 34, hostile input): screened for pleading and harm framing, not urgency,
    # because timestamps and "deadline exceeded" errors are ordinary data.
    yield from _data_strings(message.get("evidence"), ("evidence",))
    if isinstance(message.get("options"), list):
        for i, o in enumerate(message["options"]):
            for k in ("option", "cost", "expected_effect"):
                if isinstance(o, dict) and isinstance(o.get(k), str):
                    yield ("options", i, k), o[k]
    elif isinstance(message.get("alternatives"), list):
        for i, a in enumerate(message["alternatives"]):
            if isinstance(a, str):
                yield ("alternatives", i), a


def _normal(text: str) -> str:
    """Fold look-alike characters and drop invisible ones, so spacing tricks cannot slip past."""
    return unicodedata.normalize("NFKC", text).translate(_INVISIBLE)


def _strip(text: str, quoted) -> str:
    text = _normal(text)
    for q in sorted((_normal(q) for q in quoted), key=len, reverse=True):
        text = re.sub(re.escape(q), " ", text, flags=re.I)
    return text


def screen(message: dict, quoted=()) -> list[dict]:
    """Every rule broken by GREG's own words: [{field, rule, matched}]."""
    evidenced_deadline = bool(message.get("deadline")) and bool(message.get("deadline_evidence"))
    found = []
    for path, text in _prose(message):
        bare = _strip(text, quoted)
        for rule, pattern in RULES:
            if rule == "manufactured_urgency" and (evidenced_deadline or path[0] == "evidence"):
                continue
            hit = pattern.search(bare)
            if hit:
                found.append({"field": list(path), "rule": rule, "matched": hit.group(0)})
    return found


def _withhold(message: dict, violations: list[dict]) -> dict:
    out = {**message}
    rules = sorted({v["rule"] for v in violations})
    note = "wording withheld (" + ", ".join(rules) + ")"
    for v in violations:
        path = v["field"]
        if path[0] == "options":
            i, k = path[1], path[2]
            out["options"] = [dict(o) for o in out["options"]]
            out["options"][i][k] = f"option {i + 1}: {note}" if k == "option" else note
        elif path[0] == "alternatives":
            out["alternatives"] = list(out["alternatives"])
            out["alternatives"][path[1]] = f"option {path[1] + 1}: {note}"
        elif path[0] == "evidence":
            out["evidence"] = _set(out["evidence"], path[1:], note)
        elif path[0] == "why_now":
            out["why_now"] = (f"{message['kind']}: GREG's {note}; decide from the evidence and options, "
                              "which are unchanged")
        else:
            out[path[0]] = note
    if isinstance(out.get("options"), list):
        out["alternatives"] = [o["option"] for o in out["options"]]
    out["wording_withheld"] = {"fields": [v["field"] for v in violations], "rules": rules,
                               "original_digest": sha256_json({f: message.get(f) for f in PROSE_FIELDS
                                                               + ("options", "alternatives")})}
    return out


def _set(value, path, replacement):
    """A copy of ``value`` with the string at ``path`` replaced."""
    if not path:
        return replacement
    head, rest = path[0], path[1:]
    if isinstance(value, dict):
        return {**value, head: _set(value[head], rest, replacement)}
    return [_set(v, rest, replacement) if i == head else v for i, v in enumerate(value)]


def record(journal: Journal, message: dict, *, quoted=()) -> dict:
    """Validate, screen and record one founder ask. Returns what the founder will see."""
    validate(message)
    violations = screen(message, quoted)
    shown = message
    if violations:
        shown = _withhold(message, violations)
        journal.record("ask.wording_withheld", {"request_id": message["request_id"], "kind": message["kind"],
                                                "mission_id": message["mission_id"], "violations": violations,
                                                "original": {f: message.get(f) for f in PROSE_FIELDS
                                                             + ("options", "alternatives", "evidence")
                                                             if f in message}},
                       key=[message["request_id"], "withheld"])
    journal.record("decision.requested", shown, key=message["request_id"])
    return shown


# Asks where an answer is only a record: GREG does not act on "approve". Every surface says so,
# so a button is never mistaken for hiring someone or handing over a credential.
ANSWER_ONLY_RECORDS = {
    "HUMAN_WORK": "Your answer is only recorded; GREG contacts, hires and pays no one. The mission continues "
                  "when the deliverable is observed.",
    "ACCOUNT_ACCESS": "Your answer is only recorded; it grants nothing. Only `greg secret set` on the body gives "
                      "GREG a credential.",
    "CAPABILITY_ATTACH": "Approve or Reject only records your answer. Attaching is its own signed command: the "
                         "Attach button beside a verified candidate, or `greg attach <capability_id>`.",
}


def surface(request: dict) -> dict:
    """The fields every founder surface (console, phone, status, morning report) shows."""
    keys = ("request_id", "kind", "mission_id", "resource", "why_now", "recommendation", "expected_effect",
            "options", "alternatives", "uncertainty", "authority_requested", "evidence",
            "consequence_of_no_response", "deadline", "deadline_evidence", "wording_withheld")
    shown = {k: request[k] for k in keys if k in request}
    if request.get("kind") in ANSWER_ONLY_RECORDS:
        shown["answer_effect"] = ANSWER_ONLY_RECORDS[request["kind"]]
    return shown
