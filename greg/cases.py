"""A request-led case assessed against a founder-signed rulebook (the operational slice, 2026-11-12).

A third party asks to be paid for completed work. ``case.assess`` reads the case folder against a rulebook that is
data, signed with the mission by its sha256: which documents a case needs, which fact each document carries under
which key, the rules over those facts, what holds a case as disputed, when completion counts as accepted, what is
settled, what the estimate column shows, and how each state is routed. No rule lives in this module. It extracts
typed facts with their sources, evaluates the rulebook's conditions three-valued and reports, deriving everything and
inventing nothing:

* A fact is known, absent (an optional document not on file) or unknown, and unknown says why: the document is not
  on file, the key is not in it, it is not readable text (``faithful_text``), the data plane quarantined it
  (greg.dataplane), the value does not parse as its type, or two documents give different values (a conflict: both
  values are kept with their sources and GREG picks neither). A document read but silent on a fact makes no claim;
  a claim that cannot be read may disagree, so a rule reading that fact waits on it even from another document.
* A rule is met, not_met or unknown, and unknown names exactly the facts it waits on, or why the facts on file cannot
  decide it (``undecidable``: two kinds of value compared, a division by zero, an order on absence). Eligibility is
  eligible (every rule met), ineligible (some rule not met; unknown rules then do not matter) or undetermined (none
  failed, some unknown). A value the facts cannot settle is left out of the output's ``decided`` fields
  (``complete: false``), so no mission check reads an unknown as a pass or as a failure. A rulebook that compares two
  kinds of value is refused when it is signed.
* Payment is observed only by business.reconcile's own matching (greg.business_loop.reconcile) of exactly one
  statement row. Anything else is "not known", with its reason; only "no statement yet" and "no posting names the
  case" are measured absences, and a statement GREG cannot settle on (other columns, two postings, another amount)
  decides no check. The accounting projection keeps estimates, the reconciled actual and the unknown in three
  separate columns; the actual column is read from the statement row.
* A duplicate is read from the body's own ledger: an earlier case mission (any mission whose case.assess checks read
  the same reference, compared by business_loop.reference_key) that is open or settled, named with a pointer to the
  first.

``case.packet`` delivers one new packet per assessment (Markdown and a JSON twin) into the founder's delivery root
and says what changed since the mission's previous packet. An earlier packet is never overwritten.

Text in documents is data: only the keys the rulebook declares are read, an instruction-shaped line steers nothing,
and a document the data plane quarantines contributes no fact. The documents and rulebooks this module was built and
tested with are synthetic.
"""
from __future__ import annotations

import ast
from datetime import date
import decimal
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

from greg.capabilities import CapabilityError, InvocationContext, _inside, bounded_read, faithful_text
from greg.textform import canon
from provenance.digests import sha256_json

RENDERER = "greg.cases/2"   # 2: absence, undecidable rules and conflicts no rule reads are rendered
TYPES = ("text", "amount", "number", "percent", "date", "yes_no")
STATES = ("eligible", "ineligible", "undetermined", "disputed")
BUILTIN = {"mission": ("reference",), "ledger": ("earlier cases",)}   # sources that are not documents
YES, NO = {"yes", "y", "true"}, {"no", "n", "false"}
FUNCTIONS = ("sum", "count", "min", "max", "abs", "date")
NAME = re.compile(r"[a-z][a-z0-9_]{0,47}")
LINE = re.compile(r"^\s*([^:\n]{1,80}?)\s*:\s*(.*?)\s*$")
MAX_CONDITION = 600


class EventReader:
    """The body's journal, readable and nothing else: ``replay`` and ``find``. A case reads its request, earlier
    cases and its own receipts through it; it is handed no ``record`` and no ledger it could write through."""

    __slots__ = ("_replay", "_find")

    def __init__(self, journal):
        self._replay, self._find = journal.replay, journal.ledger.find

    def replay(self, prefix: str = ""):
        return self._replay(prefix)

    def find(self, record_hash: str):
        return self._find(record_hash)


# -- the rulebook -----------------------------------------------------------------------------------------------

def _key(text: str) -> str:
    """A document key as compared: one normalization form, case-folded, whitespace runs as one space."""
    return " ".join(canon(str(text)).casefold().split())


def _names(condition: str) -> set[str]:
    """The facts a condition reads, after checking it uses only the rulebook language: literals, facts, + - * /,
    comparisons (== != < <= > >= in, not in), and / or / not, and the functions in FUNCTIONS."""
    if not isinstance(condition, str) or not condition.strip() or len(condition) > MAX_CONDITION:
        raise CapabilityError(f"a condition is a nonblank expression of at most {MAX_CONDITION} characters")
    try:
        tree = ast.parse(condition.strip(), mode="eval")
    except SyntaxError as exc:
        raise CapabilityError(f"condition {condition!r} does not parse: {exc.msg}") from None
    names = set()
    allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.USub, ast.BinOp, ast.Add,
               ast.Sub, ast.Mult, ast.Div, ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In,
               ast.NotIn, ast.Name, ast.Load, ast.Constant, ast.Call, ast.Tuple, ast.List)
    for node in ast.walk(tree):
        if not isinstance(node, allowed):
            raise CapabilityError(f"condition {condition!r} uses {type(node).__name__}, outside the rulebook language")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS or node.keywords:
                raise CapabilityError(f"condition {condition!r} calls something other than {', '.join(FUNCTIONS)}")
        elif isinstance(node, ast.Name) and not any(isinstance(p, ast.Call) and p.func is node for p in ast.walk(tree)):
            names.add(node.id)
        elif isinstance(node, ast.Constant) and not isinstance(node.value, (str, int, float, bool, type(None))):
            raise CapabilityError(f"condition {condition!r} holds a literal of an unsupported type")
    return names


KINDS = {"text": "text", "amount": "number", "number": "number", "percent": "number", "date": "date",
         "yes_no": "truth value"}


def _kind(node, facts: dict) -> str | None:
    """The kind of value an expression of the rulebook language yields, where it is fixed by the rulebook (None:
    absence, or not fixed)."""
    if isinstance(node, ast.Constant):
        value = node.value
        return None if value is None else "truth value" if isinstance(value, bool) else \
            "text" if isinstance(value, str) else "number"
    if isinstance(node, ast.Name):
        spec = facts.get(node.id)
        return None if spec is None else "list" if spec.get("many") else KINDS[spec["type"]]
    if isinstance(node, ast.Call):
        return "date" if node.func.id == "date" else "number"
    if isinstance(node, ast.BinOp) or isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return "number"
    if isinstance(node, (ast.BoolOp, ast.Compare, ast.UnaryOp)):
        return "truth value"
    return "list" if isinstance(node, (ast.List, ast.Tuple)) else None


def _typecheck(condition: str, facts: dict) -> None:
    """Refuse, at signing, a comparison between two kinds of value (a date fact against text, a yes/no fact against
    'yes') and an order on text or truth values: evaluated, each is undecidable, so a typo would hold every case."""
    for node in ast.walk(ast.parse(condition.strip(), mode="eval")):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        for op, right in zip(node.ops, node.comparators):
            a, b = _kind(left, facts), _kind(right, facts)
            if isinstance(op, (ast.In, ast.NotIn)):
                for element in right.elts if isinstance(right, (ast.List, ast.Tuple)) else []:
                    kind = _kind(element, facts)
                    if a not in (None, "list") and kind is not None and kind != a:
                        raise CapabilityError(f"condition {condition!r} looks for a {a} among {kind} values")
            elif a is not None and b is not None and a != b:
                raise CapabilityError(f"condition {condition!r} compares a {a} with a {b}")
            elif not isinstance(op, (ast.Eq, ast.NotEq)) and (a or b) in ("text", "truth value", "list"):
                raise CapabilityError(f"condition {condition!r} orders a {a or b}; only numbers and dates have an order")
            left = right


def _needs(spec: dict, facts: dict, where: str) -> dict:
    needs = spec.get("needs")
    if not isinstance(needs, dict) or not needs:
        raise CapabilityError(f"{where} must say which facts it needs, from which document kinds")
    out = {}
    for fact, kinds in needs.items():
        kinds = [kinds] if isinstance(kinds, str) else kinds
        if fact not in facts:
            raise CapabilityError(f"{where} needs {fact!r}, which the rulebook does not declare")
        if not isinstance(kinds, list) or not kinds or not set(kinds) <= set(facts[fact]["from"]):
            raise CapabilityError(f"{where} needs {fact!r} from kinds that do not carry it")
        out[fact] = list(kinds)
    return out


def load_rulebook(data: bytes) -> dict:
    """The rulebook in ``data``, checked whole before any case is read against it; CapabilityError says what is
    wrong. It is the founder's data: this checks its shape, never its policy."""
    try:
        book = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CapabilityError(f"the rulebook is not JSON: {exc}") from None
    if not isinstance(book, dict):
        raise CapabilityError("the rulebook is a JSON object")
    for field in ("rulebook", "version", "label"):
        if not isinstance(book.get(field), str) or not book[field].strip():
            raise CapabilityError(f"the rulebook states its {field}")
    if not isinstance((book.get("request") or {}).get("channel"), str):
        raise CapabilityError("the rulebook names the intake channel requests arrive on (request.channel)")
    documents = book.get("documents")
    if not isinstance(documents, dict) or not documents:
        raise CapabilityError("the rulebook lists the documents a case needs")
    for kind, doc in documents.items():
        if not NAME.fullmatch(kind) or kind in BUILTIN:
            raise CapabilityError(f"document kind {kind!r} is a short lowercase name and not one of {sorted(BUILTIN)}")
        name = (doc or {}).get("file")
        if not isinstance(name, str) or Path(name).name != name or name.startswith(".") or not name:
            raise CapabilityError(f"document {kind!r} names a plain file in the case folder")
        if not isinstance(doc.get("required"), bool):
            raise CapabilityError(f"document {kind!r} says whether it is required")
    facts = book.get("facts")
    if not isinstance(facts, dict) or not facts:
        raise CapabilityError("the rulebook declares its facts")
    for fact, spec in facts.items():
        if not NAME.fullmatch(fact) or not isinstance(spec, dict) or spec.get("type") not in TYPES:
            raise CapabilityError(f"fact {fact!r} has a short lowercase name and a type in {TYPES}")
        sources = spec.get("from")
        if not isinstance(sources, dict) or not sources:
            raise CapabilityError(f"fact {fact!r} says which document kinds carry it, under which key")
        for kind, key in sources.items():
            if kind in BUILTIN:
                if key not in BUILTIN[kind]:
                    raise CapabilityError(f"fact {fact!r}: the {kind} source offers only {BUILTIN[kind]}")
            elif kind not in documents or not isinstance(key, str) or not key.strip():
                raise CapabilityError(f"fact {fact!r}: {kind!r} is not a listed document, or its key is blank")
        for pattern in ("pattern", "only"):
            if pattern in spec:
                try:
                    re.compile(spec[pattern])
                except (re.error, TypeError):
                    raise CapabilityError(f"fact {fact!r}: {pattern} is not a regular expression") from None
    for field in ("case_reference",):
        if book.get(field) not in facts:
            raise CapabilityError(f"the rulebook's {field} is one of its facts")
    rules = book.get("rules")
    if not isinstance(rules, list) or not rules:
        raise CapabilityError("the rulebook states its rules")
    seen = set()
    for group, where in ((rules, "rule"), (book.get("disputes") or [], "dispute")):
        if not isinstance(group, list):
            raise CapabilityError(f"the rulebook's {where}s are a list")
        for item in group:
            ident = (item or {}).get("id")
            if not isinstance(ident, str) or not ident or ident in seen:
                raise CapabilityError(f"every {where} has its own id")
            seen.add(ident)
            needs = _needs(item, facts, f"{where} {ident}")
            if not _names(item.get("condition")) <= set(needs):
                raise CapabilityError(f"{where} {ident} reads a fact it does not list in needs")
            _typecheck(item["condition"], facts)
            if "name" in item and item["name"] not in facts:
                raise CapabilityError(f"{where} {ident} names a fact the rulebook does not declare")
    acceptance = book.get("acceptance")
    if not isinstance(acceptance, dict) or not _names(acceptance.get("condition")) <= set(
            _needs(acceptance, facts, "acceptance")):
        raise CapabilityError("the rulebook says when completion counts as accepted (acceptance: needs, condition)")
    _typecheck(acceptance["condition"], facts)
    settlement = book.get("settlement")
    if not isinstance(settlement, dict) or any(settlement.get(k) not in facts for k in ("amount", "currency")):
        raise CapabilityError("the rulebook names the amount and currency facts a settlement reconciles")
    if any(f not in facts for f in (book.get("estimate") or [])):
        raise CapabilityError("the estimate column lists declared facts only")
    routing = book.get("routing")
    if not isinstance(routing, list) or sorted(r.get("state") for r in routing if isinstance(r, dict)) != sorted(STATES) \
            or any(not isinstance(r.get("route"), str) or not isinstance(r.get("action"), str) for r in routing):
        raise CapabilityError(f"the routing table gives each of {STATES} once, in precedence order, with its route "
                              "and action")
    return book


# -- documents and facts ----------------------------------------------------------------------------------------

def _read_document(kind: str, spec: dict, folder: Path) -> dict:
    """One document of the case: read, absent, unreadable or quarantined, with its digest and the data plane's
    flags. Only a regular file within the read ceiling is read; anything else is unreadable, with the reason."""
    from greg.dataplane import instruction_shaped, quarantines
    path = folder / spec["file"]
    doc = {"kind": kind, "file": spec["file"], "required": spec["required"]}
    if not path.exists() and not path.is_symlink():
        return {**doc, "state": "absent"}
    try:
        data = bounded_read(path, f"{spec['file']} exceeds the read ceiling")
    except (CapabilityError, OSError) as exc:
        return {**doc, "state": "unreadable", "reason": str(exc)[:200]}
    text, how = faithful_text(data)
    doc.update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    if text is None:
        return {**doc, "state": "unreadable", "reason": f"not readable text ({how})"}
    flags = instruction_shaped(text)
    if quarantines(flags):
        return {**doc, "state": "quarantined", "flags": flags, "reason": "quarantined by the data plane: "
                + ", ".join(flags)}
    return {**doc, "state": "read", "flags": flags, "text": text}


def _parse(spec: dict, raw: str):
    """(value, None) or (None, why) for one value as its declared type."""
    from greg.business_loop import parse_amount
    text = raw.strip()
    if "pattern" in spec:
        found = re.search(spec["pattern"], text)
        if found is None:
            return None, f"{text[:60]!r} does not match the declared pattern"
        text = found.groupdict().get("value") or (found.group(1) if found.groups() else found.group(0))
    if not text:
        return None, "the value is empty"
    kind = spec["type"]
    if kind == "text":
        return " ".join(canon(text).split()), None
    if kind in ("amount", "number", "percent"):
        value = parse_amount(text[:-1] if kind == "percent" and text.endswith("%") else text)
        return (value, None) if value is not None else (None, f"{text[:60]!r} is not a number")
    if kind == "date":
        try:
            return date.fromisoformat(text), None
        except ValueError:
            return None, f"{text[:60]!r} is not a date (YYYY-MM-DD)"
    word = text.casefold()
    return (True, None) if word in YES else (False, None) if word in NO else (None, f"{text[:60]!r} is not yes or no")


def _shown(value) -> str | bool | None:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _same_key(value):
    """What two values of one fact are compared by: text case-folded, numbers and dates by value."""
    return _key(value) if isinstance(value, str) else value


def _source(fact: str, spec: dict, kind: str, docs: dict, builtin: dict) -> dict:
    """What one document kind says about one fact: values (with line and digest), absent, or unknown and why."""
    if kind in BUILTIN:
        raw = builtin[kind][spec["from"][kind]]
        if raw is None:
            return {"state": "unknown", "reason": f"the body's {kind} was not read in this assessment"}
        value, why = _parse(spec, str(raw))
        if why:
            return {"state": "unknown", "reason": why}
        return {"state": "value", "values": [{"value": value, "document": kind, "line": None}]}
    doc = docs[kind]
    if doc["state"] == "absent":
        return {"state": "absent"} if not doc["required"] else \
            {"state": "unknown", "reason": f"{doc['file']} is not on file"}
    if doc["state"] != "read":
        return {"state": "unknown", "reason": f"{doc['file']}: {doc['reason']}"}
    wanted, values = _key(spec["from"][kind]), []
    for number, line in enumerate(doc["text"].splitlines(), 1):
        found = LINE.match(line)
        if not found or _key(found.group(1)) != wanted:
            continue
        if "only" in spec and not re.search(spec["only"], found.group(2)):
            continue        # the rulebook's filter as written: a flag it wants (?i) it writes itself
        value, why = _parse(spec, found.group(2))
        if why:
            return {"state": "unknown", "reason": f"{doc['file']} line {number}: {why}"}
        values.append({"value": value, "document": kind, "file": doc["file"], "sha256": doc["sha256"],
                       "line": number})
    if not values and not spec.get("many"):
        # read, and silent on this fact: no claim to disagree with, and no value where a rule needs this document's
        return {"state": "silent", "reason": f"{doc['file']} has no {spec['from'][kind]!r} line"}
    return {"state": "value", "values": values}


def _facts(book: dict, docs: dict, builtin: dict) -> dict:
    out = {}
    for fact, spec in book["facts"].items():
        sources = {kind: _source(fact, spec, kind, docs, builtin) for kind in spec["from"]}
        values = [v for s in sources.values() if s["state"] == "value" for v in s["values"]]
        distinct = {} if spec.get("many") else {_same_key(v["value"]): v for v in values}
        unknown = {k: s["reason"] for k, s in sources.items() if s["state"] == "unknown"}
        silent = {k: s["reason"] for k, s in sources.items() if s["state"] == "silent"}
        state = ("conflict" if len(distinct) > 1 else "unknown" if unknown else
                 ("unknown" if silent else "absent") if not values and not spec.get("many") else "known")
        unknown = {**unknown, **silent} if state == "unknown" else unknown
        out[fact] = {"type": spec["type"], "many": bool(spec.get("many")), "state": state, "sources": sources,
                     **({"unknown": unknown} if unknown else {})}
        if state == "conflict":
            out[fact]["conflict"] = [{**v, "value": _shown(v["value"])} for v in values]
    return out


def _resolve(needs: dict, facts: dict) -> tuple[dict, list, list, list]:
    """(environment, missing, conflicts, absent) for one rule: the value of each needed fact from the kinds it is
    needed from; the facts still unknown and why; the needed facts two documents disagree on; and the needed facts
    whose documents are optional and not on file (their value is absence). A fact is missing where a kind the rule
    reads has no value, and also where any other document's claim to it could not be read: that claim may disagree,
    and a disagreement is a conflict, so the rule waits on it."""
    env, missing, conflicts, absent = {}, [], [], []
    for fact, kinds in needs.items():
        record = facts[fact]
        if record["state"] == "conflict":
            conflicts.append(fact)
            continue
        sources = record["sources"]
        gaps = [(k, sources[k]["reason"]) for k in kinds if sources[k]["state"] in ("unknown", "silent")]
        gaps += [(k, s["reason"]) for k, s in sources.items() if k not in kinds and s["state"] == "unknown"]
        if gaps:
            missing += [{"fact": fact, "document": k, "reason": why} for k, why in gaps]
            continue
        values = [v["value"] for k in kinds if sources[k]["state"] == "value" for v in sources[k]["values"]]
        env[fact] = values if record["many"] else (values[0] if values else None)
        if env[fact] is None:
            absent.append({"fact": fact, "documents": [k for k in kinds if sources[k]["state"] == "absent"]})
    return env, missing, conflicts, absent


# -- the rulebook language, evaluated ------------------------------------------------------------------------------

class _Undecidable(Exception):
    pass


def _number(value):
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise _Undecidable(f"{_shown(value)!r} is not a number")
    return value


def _equal(a, b) -> bool:
    """Equality of two values of one kind; absence (an optional document not on file) equals only absence. Two
    kinds (a date and a text) are not compared: that is undecidable, never silently false (a rulebook typo)."""
    if a is None or b is None:
        return a is b
    if isinstance(a, str) and isinstance(b, str):
        return _key(a) == _key(b)
    if type(a) is not type(b):
        raise _Undecidable(f"{_shown(a)!r} and {_shown(b)!r} are not the same kind of value")
    return a == b


def _compare(op, a, b) -> bool:
    if isinstance(op, ast.Eq):
        return _equal(a, b)
    if isinstance(op, ast.NotEq):
        return not _equal(a, b)
    if isinstance(op, (ast.In, ast.NotIn)):
        if not isinstance(b, list):
            raise _Undecidable("'in' needs a list on its right")
        found = any(_equal(a, x) for x in b)
        return found if isinstance(op, ast.In) else not found
    ordered = (isinstance(a, Decimal) and isinstance(b, Decimal) and not isinstance(a, bool)) or \
        (isinstance(a, date) and isinstance(b, date))
    if not ordered:
        raise _Undecidable(f"{_shown(a)!r} and {_shown(b)!r} have no order")
    return {ast.Lt: a < b, ast.LtE: a <= b, ast.Gt: a > b, ast.GtE: a >= b}[type(op)]


def _eval(node, env):
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.Constant):
        value = node.value
        return Decimal(str(value)) if isinstance(value, (int, float)) and not isinstance(value, bool) else value
    if isinstance(node, ast.Name):
        return env[node.id]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_eval(e, env) for e in node.elts]
    if isinstance(node, ast.UnaryOp):
        value = _eval(node.operand, env)
        if isinstance(node.op, ast.Not):
            if not isinstance(value, bool):
                raise _Undecidable("'not' needs a truth value")
            return not value
        return -_number(value)
    if isinstance(node, ast.BoolOp):
        values = [_eval(v, env) for v in node.values]
        if not all(isinstance(v, bool) for v in values):
            raise _Undecidable("'and' and 'or' need truth values")
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.BinOp):
        a, b = _number(_eval(node.left, env)), _number(_eval(node.right, env))
        return {ast.Add: lambda: a + b, ast.Sub: lambda: a - b, ast.Mult: lambda: a * b,
                ast.Div: lambda: a / b}[type(node.op)]()
    if isinstance(node, ast.Compare):
        left = _eval(node.left, env)
        for op, right_node in zip(node.ops, node.comparators):
            right = _eval(right_node, env)
            if not _compare(op, left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        args = [_eval(a, env) for a in node.args]
        name = node.func.id
        if name == "date":
            if len(args) != 1 or not isinstance(args[0], str):
                raise _Undecidable("date() takes one YYYY-MM-DD text")
            return date.fromisoformat(args[0])
        if name == "abs":
            if len(args) != 1:
                raise _Undecidable("abs() takes one number")
            return abs(_number(args[0]))
        if len(args) != 1 or not isinstance(args[0], list):
            raise _Undecidable(f"{name}() takes one list")
        items = args[0]
        if name == "count":
            return Decimal(len(items))
        numbers = [_number(v) for v in items]
        if name == "sum":
            return sum(numbers, Decimal(0))
        if not numbers:
            raise _Undecidable(f"{name}() of an empty list")
        return min(numbers) if name == "min" else max(numbers)
    raise _Undecidable(f"{type(node).__name__} is outside the rulebook language")


def evaluate(condition: str, needs: dict, facts: dict) -> dict:
    """One condition, three-valued: met, not_met, or unknown with exactly the facts it waits on (or why the facts it
    has cannot decide it). Never a pass or a failure on an unknown."""
    env, missing, conflicts, absent = _resolve(needs, facts)
    used = {f: ([_shown(v) for v in value] if isinstance(value, list) else _shown(value)) for f, value in env.items()}
    shown_absent = {"absent": absent} if absent else {}     # a value of None is an optional document not on file
    if missing or conflicts:
        return {"state": "unknown", "facts_used": used, "missing": missing, "conflicts": conflicts, **shown_absent}
    try:
        result = _eval(ast.parse(condition.strip(), mode="eval"), env)
    except (_Undecidable, ArithmeticError, decimal.DecimalException, ValueError, TypeError) as exc:
        return {"state": "unknown", "facts_used": used, "missing": [], "conflicts": [], **shown_absent,
                "reason": f"the condition cannot be decided on these facts: {exc}"[:300]}
    if not isinstance(result, bool):
        return {"state": "unknown", "facts_used": used, "missing": [], "conflicts": [], **shown_absent,
                "reason": "the condition does not yield true or false"}
    return {"state": "met" if result else "not_met", "facts_used": used, **shown_absent}


# -- the assessment -----------------------------------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:40] or "case"


def assessment_digest(value) -> str:
    """The digest an assessment is named and re-derived by: sorted-key compact JSON, non-ASCII kept as text."""
    return sha256_json(value, ensure_ascii=False, default=str)


def _requests(journal, channel: str, reference: str) -> list | None:
    """The intake records on the rulebook's channel that carry the case reference, oldest first (greg.dataplane:
    retained as untrusted data, never a command). None: this reading has no journal."""
    if journal is None:
        return None
    from greg.business_loop import carries_reference
    return [{"event_id": e.event_id, "source": e.payload.get("source"), "content_sha256": e.payload.get("content_sha256"),
             "at": e.payload.get("at"), "quarantined": e.payload.get("quarantined"),
             "instruction_flags": e.payload.get("instruction_flags")}
            for e in journal.replay("external.ingested")
            if e.payload.get("channel") == channel and carries_reference(str(e.payload.get("content", "")), reference)]


def case_reference(spec: dict) -> str | None:
    """The case reference a mission assesses: what its case.assess checks read, signed in the mission, whatever made
    it (the request-case template, a ratified procedure's run, a hand-written spec). None: not a case."""
    references = {(check.get("sensor") or {}).get("params", {}).get("reference")
                  for check in spec.get("success_checks") or [] if isinstance(check, dict)
                  and (check.get("sensor") or {}).get("capability") == "case.assess"}
    return next(iter(references)) if len(references) == 1 and isinstance(next(iter(references)), str) else None


def _earlier_cases(journal, reference: str, mission_id: str) -> list | None:
    """Case missions (case_reference) registered on this body before this one for the same reference that are open
    or settled (abandoned and superseded ones are neither), first first. References are compared by
    business_loop.reference_key. None: this reading has no journal."""
    from greg.business_loop import reference_key
    if journal is None:
        return None
    wanted, cases, closed, earlier = reference_key(reference), [], {}, True
    for event in journal.replay("mission."):
        data = event.payload
        mid = data.get("mission_id")
        if event.type == "greg.mission.registered":
            earlier = earlier and mid != mission_id   # only those registered before this mission count as earlier
            if not earlier:
                continue
            theirs = case_reference(data.get("spec") or {})
            if theirs is not None and reference_key(theirs) == wanted:
                cases.append({"mission_id": mid, "registered_event": event.event_id})
        elif event.type == "greg.mission.achieved":
            closed.setdefault(mid, "settled")
        elif event.type == "greg.mission.lifecycle" and data.get("state") in ("ABANDONED", "SUPERSEDED"):
            closed[mid] = data["state"].lower()
    found = []
    for case in cases:
        state = closed.get(case["mission_id"], "open")
        if state in ("open", "settled"):
            found.append({**case, "state": state})
    return found


def _payment(book: dict, facts: dict, params: dict, reference: str, ctx: InvocationContext) -> dict:
    """The statement read by business.reconcile's own matching, as observed or not known, with the reason."""
    from greg.business_loop import parse_amount, reconcile
    settle = book["settlement"]
    if not params.get("statement"):
        return {"state": "unknown", "observed": False, "decided": False,
                "reason": "not known: no statement file was signed with this assessment"}
    needs = {settle[k]: list(book["facts"][settle[k]]["from"]) for k in ("amount", "currency")}
    env, missing, conflicts, _ = _resolve(needs, facts)
    if missing or conflicts or env.get(settle["amount"]) is None or not isinstance(env.get(settle["currency"]), str):
        return {"state": "unknown", "observed": False, "decided": False,
                "reason": "the amount or currency to reconcile is not known yet: " + "; ".join(
                    [f"{m['fact']} ({m['document']}): {m['reason']}" for m in missing]
                    + [f"{c}: documents disagree" for c in conflicts]) if missing or conflicts else
                "the amount or currency to reconcile is not known yet"}
    amount, currency = env[settle["amount"]], env[settle["currency"]]
    try:
        seen = reconcile({"path": params["statement"], "amount": format(amount, "f"), "currency": currency,
                          "reference": reference, **({"columns": params["columns"]} if params.get("columns") else {}),
                          **({"minor_units": True} if params.get("minor_units") else {})}, ctx)
    except (CapabilityError, OSError) as exc:
        return {"state": "unknown", "observed": False, "decided": False, "expected": format(amount, "f"),
                "currency": currency, "reason": f"the statement could not be reconciled: {exc}"[:300]}
    expected = {"expected": format(amount, "f"), "currency": currency, "reconcile": seen}
    if seen.get("matched"):
        posting = seen.get("posting") or {}
        actual = parse_amount(str(posting.get("amount")), minor_units=bool(params.get("minor_units")))
        return {**expected, "state": "observed", "observed": True, "decided": True,
                "reason": seen["detail"], "actual": {"amount": _shown(actual), "currency": posting.get("currency"),
                                                     "statement": seen["path"], "statement_sha256": seen["sha256"],
                                                     "row": seen["row"], "row_sha256": seen["row_sha256"]}}
    if seen.get("complete") is False:
        return {**expected, "state": "unknown", "observed": False, "decided": False,
                "reason": f"not known: {seen['detail']}"}
    if seen.get("exists") is False:
        why = "not known: no statement exported yet, so no payment is observed"
    elif seen.get("missing_columns") or seen.get("matches", 0) > 1 or seen.get("near_misses"):
        # The statement was not read for this reference (its columns are not the signed ones), or it shows postings
        # carrying the reference that GREG cannot settle on (two of them; another amount or currency). Payment is
        # not known either way, so no check reads it as not paid and nobody is asked to pay again on it.
        return {**expected, "state": "unknown", "observed": False, "decided": False,
                "reason": "not known: " + seen["detail"]}
    else:
        why = f"not known yet: {seen['detail']}"
    return {**expected, "state": "unknown", "observed": False, "decided": True, "reason": why}


def _route(book: dict, eligibility: str, disputes: list, disputes_unknown: list, failed: list, unresolved: list,
           duplicates: list, undecidable: list, other_conflicts: list) -> dict:
    holds = {"disputed": bool(disputes), "ineligible": eligibility == "ineligible",
             "undetermined": eligibility == "undetermined" or (eligibility == "eligible" and bool(disputes_unknown)),
             "eligible": eligibility == "eligible" and not disputes_unknown}
    entry = next(r for r in book["routing"] if holds[r["state"]])
    unread = f"; documents disagree on {', '.join(c['fact'] for c in other_conflicts)}, which no rule reads (shown " \
             "in the packet, not held)" if other_conflicts else ""
    reasons = {"disputed": "; ".join(d["name"] for d in disputes),
               "ineligible": "; ".join(f"rule {r['id']} not met: {r['description']}" for r in failed)
               + (f"; first case with this reference: {duplicates[0]['mission_id']} ({duplicates[0]['state']})"
                  if duplicates else ""),
               "undetermined": "; ".join(unresolved + undecidable) or "; ".join(disputes_unknown)
               or "a rule cannot be decided on the facts it has",
               "eligible": "every rule is met" + unread}
    return {"state": entry["state"], "route": entry["route"], "action": entry["action"],
            "reason": reasons[entry["state"]][:1000]}


def assess(params: dict, ctx: InvocationContext) -> dict:
    """``case.assess``: the case folder read against the signed rulebook. Read-only; everything is derived."""
    roots = ctx.read_roots + (ctx.workspace,)
    rulebook_path = _inside(Path(params["rulebook"]), roots)
    raw = bounded_read(rulebook_path, "the rulebook exceeds the read ceiling")
    signed = str(params.get("rulebook_sha256", ""))
    if hashlib.sha256(raw).hexdigest() != signed:
        raise CapabilityError("the rulebook differs from the one signed with the mission; nothing was assessed")
    book = load_rulebook(raw)
    folder = _inside(Path(params["folder"]), roots)
    reference = " ".join(str(params["reference"]).split())
    if len(reference) < 6:
        raise CapabilityError("the case reference must be at least 6 characters")
    journal = ctx.journal
    duplicates = _earlier_cases(journal, reference, ctx.mission_id)
    docs = {kind: _read_document(kind, spec, folder) for kind, spec in book["documents"].items()}
    builtin = {"mission": {"reference": reference},
               "ledger": {"earlier cases": len(duplicates) if duplicates is not None else None}}
    facts = _facts(book, docs, builtin)
    rules = []
    for rule in book["rules"]:
        needs = _needs(rule, book["facts"], f"rule {rule['id']}")
        rules.append({"id": rule["id"], "description": rule.get("description", ""),
                      **evaluate(rule["condition"], needs, facts)})
    failed = [r for r in rules if r["state"] == "not_met"]
    eligibility = "ineligible" if failed else "undetermined" if any(r["state"] == "unknown" for r in rules) \
        else "eligible"
    needed = {f for item in (book["rules"] + (book.get("disputes") or []) + [book["acceptance"]])
              for f in item["needs"]} | {book["settlement"][k] for k in ("amount", "currency")}
    conflicts = [{"fact": f, "values": facts[f]["conflict"]} for f in sorted(needed) if facts[f]["state"] == "conflict"]
    # documents that disagree on a fact no rule, dispute, acceptance or settlement reads: shown, never silently
    # dropped; whether such a disagreement should hold a case is the rulebook's to say (it would read the fact)
    other_conflicts = [{"fact": f, "values": facts[f]["conflict"]} for f in sorted(set(facts) - needed)
                       if facts[f]["state"] == "conflict"]
    disputes = [{"kind": "conflict", "fact": c["fact"], "values": c["values"],
                 "name": f"{c['fact']}: " + " vs ".join(f"{v['value']} ({v.get('file', v['document'])}"
                                                         + (f" line {v['line']})" if v.get("line") else ")")
                                                         for v in c["values"])} for c in conflicts]
    disputes_unknown, dispute_checks = [], []
    for item in book.get("disputes") or []:
        seen = evaluate(item["condition"], _needs(item, book["facts"], f"dispute {item['id']}"), facts)
        dispute_checks.append({"id": item["id"], "description": item.get("description", ""), **seen})
        if seen["state"] == "met":
            named = facts.get(item.get("name"), {})
            value = next((v["value"] for s in named.get("sources", {}).values() if s["state"] == "value"
                          for v in s["values"]), None) if named.get("state") == "known" else None
            disputes.append({"kind": "dispute", "id": item["id"], "description": item.get("description", ""),
                             "name": f"{item['id']}: {item.get('description', '')}"
                             + (f" ({_shown(value)})" if value is not None else "")})
        elif seen["state"] == "unknown":
            disputes_unknown.append(f"dispute {item['id']} cannot be decided: " + "; ".join(
                [f"{m['fact']} ({m['document']}): {m['reason']}" for m in seen["missing"]]
                + [f"{c}: documents disagree" for c in seen["conflicts"]] + ([seen["reason"]] if "reason" in seen
                                                                             else [])))
    acceptance = {"description": book["acceptance"].get("description", ""),
                  **evaluate(book["acceptance"]["condition"], _needs(book["acceptance"], book["facts"], "acceptance"),
                             facts)}
    accepted = {"met": True, "not_met": False}.get(acceptance["state"])
    unresolved = []
    if eligibility != "ineligible":
        gaps = [m for r in rules if r["state"] == "unknown" for m in r["missing"]] if eligibility == "undetermined" \
            else []
        gaps += [m for d in dispute_checks if d["state"] == "unknown" for m in d["missing"]]
        gaps += acceptance.get("missing", []) if acceptance["state"] == "unknown" else []
        unresolved = sorted({f"{m['fact']} from {m['document']}: {m['reason']}" for m in gaps})
    # A condition the facts on file cannot decide although none is missing (two kinds of value compared, a division
    # by zero, an order on an absent optional document): no fact is missing, and the evidence is not complete
    # either. The requester cannot supply it; the rulebook decides it.
    undecidable = []
    if eligibility != "ineligible":
        waiting = ([("rule " + r["id"], r) for r in rules] if eligibility == "undetermined" else []) \
            + [("dispute " + d["id"], d) for d in dispute_checks] + [("acceptance", acceptance)]
        undecidable = [f"{name} cannot be decided on the facts on file (no fact is missing; the rulebook decides "
                       f"it, not the requester): {item['reason']}" for name, item in waiting
                       if item["state"] == "unknown" and item.get("reason")]
    payment = _payment(book, facts, params, reference, ctx)
    if duplicates:
        # a posting carrying this reference belongs to the earlier case: it is never counted a second time here
        first = duplicates[0]
        payment = {**{k: v for k, v in payment.items() if k != "actual"}, "state": "unknown", "observed": False,
                   "decided": True, "reason": f"not counted for this case: {first['mission_id']} ({first['state']}) is "
                                              "an earlier case with this reference, and a posting carrying it is that "
                                              "case's"}
    estimate = []
    for fact in book.get("estimate") or []:
        # each document's own figure with its line, whatever another document says or omits; a figure a document
        # carries unreadably is a not-known row of its own; a fact no document gives is one not-known row
        record = facts[fact]
        state = {"fact_state": record["state"]} if record["state"] != "known" else {}
        rows = [{"fact": fact, "amount": _shown(v["value"]), "file": v.get("file"), "line": v.get("line"), **state}
                for s in record["sources"].values() if s["state"] == "value" for v in s["values"]]
        rows += [{"fact": fact, "amount": None, "not_known": s["reason"], "document": kind}
                 for kind, s in record["sources"].items() if s["state"] == "unknown"]
        estimate += rows or ([] if record["state"] == "known" else
                             [{"fact": fact, "amount": None, "not_known": record["state"]}])
    projection = {"currency": payment.get("currency"), "estimate": estimate,
                  "actual": [payment["actual"]] if payment["state"] == "observed" else [],
                  "unknown": [] if payment["state"] == "observed" else [{"reason": payment["reason"]}]}
    request = _requests(journal, book["request"]["channel"], reference)
    route = _route(book, eligibility, disputes, disputes_unknown, failed, unresolved, duplicates or [], undecidable,
                   other_conflicts)
    shown_docs = {k: {key: v for key, v in d.items() if key != "text"} for k, d in docs.items()}
    out = {"synthetic_label": book["label"], "reference": reference, "mission_id": ctx.mission_id,
           "rulebook": {"name": book["rulebook"], "version": book["version"], "path": str(rulebook_path),
                        "sha256": signed},
           "folder": str(folder), "documents": shown_docs,
           "facts": {f: {**r, "sources": {k: ({**s, "values": [{**v, "value": _shown(v["value"])} for v in s["values"]]}
                                              if s["state"] == "value" else s) for k, s in r["sources"].items()}}
                     for f, r in facts.items()},
           "conflicts": conflicts, "other_conflicts": other_conflicts, "rules": rules, "eligibility": eligibility,
           "failed_rules": [r["id"] for r in failed], "unresolved": unresolved, "undecidable": undecidable,
           "disputes": disputes,
           "disputes_undecided": disputes_unknown, "dispute_checks": dispute_checks, "duplicates": duplicates,
           "acceptance": acceptance, "accepted": accepted, "payment": payment,
           "payment_observed": payment["state"] == "observed", "projection": projection,
           "request": {"channel": book["request"]["channel"], "records": request},
           "request_recorded": bool(request), "route": route}
    out["assessment_digest"] = assessment_digest(out)
    name = f"case-{_slug(reference)}-{out['assessment_digest'][7:23]}"
    folder_out = Path(ctx.deliver_root).resolve() / "cases" if ctx.deliver_root else None
    current = folder_out is not None and _packet_on_disk(folder_out, name, out["assessment_digest"])
    out.update(packet={"name": name, "delivered": current}, packet_current=current)
    undecided = {k for k, open_ in (("eligibility", eligibility == "undetermined"),
                                    ("unresolved", bool(undecidable) and not unresolved),
                                    ("disputes", bool(disputes_unknown)), ("accepted", accepted is None),
                                    ("payment_observed", not payment["decided"]),
                                    ("request_recorded", request is None), ("duplicates", duplicates is None))
                 if open_}
    out["complete"] = not undecided
    if undecided:
        out["decided"] = sorted(set(out) - undecided - {"complete"})
    return out


def _packet_on_disk(folder: Path, name: str, digest: str) -> bool:
    path = folder / name / "packet.json"
    try:
        return path.is_file() and json.loads(path.read_text(encoding="utf-8"))["assessment"]["assessment_digest"] \
            == digest and (folder / name / "packet.md").is_file()
    except (OSError, ValueError, KeyError, TypeError):
        return False


# -- the packet ---------------------------------------------------------------------------------------------------

def _receipts(journal, mission_id: str, capability: str):
    """(event, receipt record) of each DONE action or observation of ``capability`` in this mission, in order."""
    out = []
    for prefix, status in (("mission.action", "DONE"), ("mission.observed", None)):
        for event in journal.replay(prefix):
            data = event.payload
            if data.get("mission_id") != mission_id or data.get("capability") != capability or not data.get("receipt"):
                continue
            if status and data.get("status") != status:
                continue
            record = journal.find(data["receipt"])
            if record is not None and record.record_type == "receipt":
                out.append((event, record))
    return out


def _previous(journal, mission_id: str, digest: str) -> tuple[dict | None, str | None]:
    """The mission's latest delivered packet for another assessment, and its receipt."""
    if journal is None or not mission_id:
        return None, None
    for event, record in reversed(_receipts(journal, mission_id, "case.packet")):
        content = ((record.payload.get("result") or {}).get("output") or {}).get("packet")
        if isinstance(content, dict) and content.get("assessment", {}).get("assessment_digest") != digest:
            return content, record.hash
    return None, None


def changes(before: dict | None, after: dict) -> list[str]:
    """What differs between two assessments, in fixed order: documents, facts, rules, eligibility, disputes, route,
    acceptance, payment, duplicates and the request."""
    if before is None:
        return ["first packet for this mission"]
    out = []
    for kind in sorted(set(before["documents"]) | set(after["documents"])):
        a, b = before["documents"].get(kind, {}), after["documents"].get(kind, {})
        if (a.get("state"), a.get("sha256")) != (b.get("state"), b.get("sha256")):
            out.append(f"document {kind}: {a.get('state')} -> {b.get('state')}"
                       + (f" (sha256 {b['sha256'][:16]})" if b.get("sha256") else ""))
    for fact in sorted(set(before["facts"]) | set(after["facts"])):
        a, b = before["facts"].get(fact, {}), after["facts"].get(fact, {})
        if _fact_view(a) != _fact_view(b):
            out.append(f"fact {fact}: {_fact_view(a)} -> {_fact_view(b)}")
    rules_before = {r["id"]: r["state"] for r in before["rules"]}
    for rule in after["rules"]:
        if rules_before.get(rule["id"]) != rule["state"]:
            out.append(f"rule {rule['id']}: {rules_before.get(rule['id'])} -> {rule['state']}")
    for field in ("eligibility", "accepted", "payment_observed", "request_recorded"):
        if before.get(field) != after.get(field):
            out.append(f"{field}: {before.get(field)} -> {after.get(field)}")
    for field, label in (("disputes", "disputes"), ("duplicates", "earlier cases with this reference")):
        a = sorted(d.get("name", d.get("mission_id", "")) for d in before.get(field) or [])
        b = sorted(d.get("name", d.get("mission_id", "")) for d in after.get(field) or [])
        if a != b:
            out.append(f"{label}: {a or 'none'} -> {b or 'none'}")
    if before["route"]["state"] != after["route"]["state"]:
        out.append(f"route: {before['route']['route']} -> {after['route']['route']}")
    if before["payment"].get("reason") != after["payment"].get("reason"):
        out.append(f"payment: {before['payment'].get('reason')} -> {after['payment'].get('reason')}")
    if len(before["request"]["records"] or []) != len(after["request"]["records"] or []):
        out.append(f"requests on file: {len(before['request']['records'] or [])} -> "
                   f"{len(after['request']['records'] or [])}")
    return out or ["no fact, rule or state changed (a file was rewritten with the same meaning)"]


def _fact_view(record: dict) -> str:
    if not record:
        return "not declared"
    if record.get("state") == "conflict":
        return "conflict"
    values = [v["value"] for s in record.get("sources", {}).values() if s.get("state") == "value" for v in s["values"]]
    return f"{record['state']} {values}" if values else record["state"]


def _accepted_line(a: dict) -> str:
    """Accepted, refused in writing, no acceptance on file, or not known: a document not on file is never shown in
    the form of a refusal."""
    acceptance = a["acceptance"]
    if a["accepted"] is None:
        return "not known"
    if a["accepted"]:
        return "yes"
    files = [a["documents"][k]["file"] for entry in acceptance.get("absent", []) for k in entry["documents"]
             if k in a["documents"]]
    if files:
        return f"not yet: no written acceptance is on file ({', '.join(sorted(set(files)))} not on file)"
    used = ", ".join(f"{k}: {v}" for k, v in sorted(acceptance.get("facts_used", {}).items()))
    return f"no, the written response does not accept completion ({used})"


def _json(content: dict) -> str:
    return json.dumps(content, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def render(content: dict) -> str:
    """The packet as Markdown, from its JSON twin alone (the appraiser re-renders it from the receipt)."""
    a = content["assessment"]
    label = content["label"]
    lines = [f"# Case packet {a['reference']}", "", f"**{label}**", "",
             f"- Mission: {content['mission_id'] or 'none'}", f"- Rulebook: {a['rulebook']['name']} "
             f"{a['rulebook']['version']} (sha256 {a['rulebook']['sha256']})",
             f"- Assessment: {a['assessment_digest']}", f"- Renderer: {content['renderer']}", "",
             "## Next action", "",
             f"**{a['route']['route']}** ({a['route']['state']}): {a['route']['action']}", "",
             f"Why: {a['route']['reason']}", "",
             f"Eligibility: **{a['eligibility']}**", "", "## Request", ""]
    records = a["request"]["records"]
    if records is None:
        lines.append("Not read: this assessment had no journal.")
    elif not records:
        lines.append(f"No request carrying {a['reference']} is on file on channel {a['request']['channel']}.")
    for r in records or []:
        lines.append(f"- {r['source']} on {a['request']['channel']} at {r['at']}, content sha256 "
                     f"{r['content_sha256']}" + (", QUARANTINED by the data plane" if r.get("quarantined") else "")
                     + (f", flags {r['instruction_flags']}" if r.get("instruction_flags") else "")
                     + f" (event {r['event_id']})")
    lines += ["", "## Rules", "", "| Rule | State | Facts used | Waiting on |", "| --- | --- | --- | --- |"]
    for rule in a["rules"]:
        waiting = "; ".join([f"{m['fact']} from {m['document']}: {m['reason']}" for m in rule.get("missing", [])]
                            + [f"{c}: documents disagree" for c in rule.get("conflicts", [])]
                            + ([rule["reason"]] if rule.get("reason") else []))
        used = ", ".join(f"{k}={'absent (not on file)' if v is None else v}"
                         for k, v in sorted(rule["facts_used"].items()))
        lines.append(f"| {rule['id']}: {rule['description']} | {rule['state']} | {used} | {waiting} |")
    lines += ["", "## Unresolved facts", ""]
    lines += [f"- {u}" for u in a["unresolved"]] or ([] if a.get("undecidable") else ["None the decision waits on."])
    if a.get("undecidable"):
        lines += ["", "Not decidable on the facts on file:"] + [f"- {u}" for u in a["undecidable"]]
    unknown_elsewhere = sorted({f"{m['fact']} from {m['document']}: {m['reason']}" for r in a["rules"]
                                for m in r.get("missing", [])} - set(a["unresolved"]))
    if unknown_elsewhere:
        lines += ["", "Also unknown, but no decision waits on them now:"] + [f"- {u}" for u in unknown_elsewhere]
    lines += ["", "## Conflicts and disputes", ""]
    lines += [f"- {d['name']}" for d in a["disputes"]] or ([] if a.get("other_conflicts") else ["None."])
    lines += [f"- undecided: {d}" for d in a["disputes_undecided"]]
    if a.get("other_conflicts"):
        lines += ["", "Documents also disagree on facts no rule reads (shown, not held):"]
        lines += [f"- {c['fact']}: " + " vs ".join(f"{v['value']} ({v.get('file', v['document'])}"
                                                    + (f" line {v['line']})" if v.get("line") else ")")
                                                    for v in c["values"]) for c in a["other_conflicts"]]
    lines += ["", "## Earlier cases with this reference", ""]
    if a["duplicates"] is None:
        lines.append("Not read: this assessment had no journal.")
    else:
        lines += [f"- {d['mission_id']} ({d['state']}), registered in event {d['registered_event']}"
                  for d in a["duplicates"]] or ["None."]
    lines += ["", "## Facts", "", "| Fact | State | Value and source |", "| --- | --- | --- |"]
    for fact, record in sorted(a["facts"].items()):
        cells = []
        for kind, source in record["sources"].items():
            if source["state"] == "value":
                cells += [f"{v['value']} ({v.get('file') or kind}" + (f" line {v['line']}" if v.get("line") else "")
                          + ")" for v in source["values"]] or [f"none listed ({kind})"]
            else:
                cells.append(f"{source['state']} ({kind}" + (f": {source['reason']}" if source.get("reason") else "")
                             + ")")
        lines.append(f"| {fact} | {record['state']} | {'; '.join(cells)} |")
    lines += ["", "## Completion", "", f"Accepted: {_accepted_line(a)}"
              + (f" ({a['acceptance']['description']})" if a["acceptance"].get("description") else ""), "",
              "## Accounting projection", "",
              f"Currency: {a['projection']['currency'] or 'not known'}", "", "### Estimate", ""]
    for row in a["projection"]["estimate"]:
        lines.append(f"- {row['fact']}: {row['amount']} ({row['file']} line {row['line']})"
                     + (f", the fact is {row['fact_state']} across documents" if row.get("fact_state") else "")
                     if row["amount"] is not None else f"- {row['fact']}: not known"
                     + (f" in {row['document']}" if row.get("document") else "") + f" ({row['not_known']})")
    lines += ["", "### Actual (reconciled statement rows only)", ""]
    lines += [f"- {row['amount']} {row['currency']}: {row['statement']} row {row['row']} (statement sha256 "
              f"{row['statement_sha256']}, row sha256 {row['row_sha256']})" for row in a["projection"]["actual"]] \
        or ["None reconciled."]
    lines += ["", "### Unknown", ""]
    lines += [f"- {row['reason']}" for row in a["projection"]["unknown"]] or ["None."]
    lines += ["", "## What changed", ""] + [f"- {c}" for c in content["changes"]]
    if content.get("previous"):
        lines.append(f"- previous packet: {content['previous']['name']} ({content['previous']['assessment_digest']})")
    trail = content["evidence_trail"]
    lines += ["", "## Evidence trail", ""]
    lines += [f"- {f['path']}: {f['sha256'] or f['state']}" for f in trail["files"]]
    lines += [f"- receipt {r}" for r in trail["receipts"]]
    lines += [f"- intake event {e}" for e in trail["request_events"]]
    lines += ["", f"*{label}* GREG contacts, pays and commits to no one; every act toward a person is a person's.", ""]
    return "\n".join(lines)


def _deliver(folder: Path, name: str, files: dict) -> Path:
    """One new packet folder holding both files, or the identical one already there; a different one is never
    overwritten. The pair appears at once (a directory renamed into place), so an interrupted write leaves either
    nothing or the whole packet, never a Markdown file without its twin."""
    target = folder / name
    if not target.exists():
        temporary = folder / f".{name}.{os.getpid()}.tmp"
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir(mode=0o755)
        for file, data in files.items():
            fd = os.open(temporary / file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
        try:
            os.rename(temporary, target)
        except OSError:
            shutil.rmtree(temporary, ignore_errors=True)
            if not target.is_dir():
                raise
    on_disk = {p.name: p.read_bytes() for p in target.iterdir()} if target.is_dir() else None
    if on_disk != files:
        raise CapabilityError(f"a different packet already exists at {name}; nothing overwritten")
    return target


def packet(params: dict, ctx: InvocationContext) -> dict:
    """``case.packet``: assess the case now and deliver its packet, one new file pair per assessment."""
    if ctx.deliver_root is None:
        raise CapabilityError("this body has no delivery root configured")
    assessment = assess(params, ctx)
    digest = assessment["assessment_digest"]
    previous, previous_receipt = _previous(ctx.journal, ctx.mission_id, digest)
    observed = [record.hash for event, record in (_receipts(ctx.journal, ctx.mission_id, "case.assess")
                                                  if ctx.journal is not None and ctx.mission_id else [])
                if ((record.payload.get("result") or {}).get("output") or {}).get("assessment_digest") == digest][:1]
    files = [{"path": assessment["rulebook"]["path"], "sha256": assessment["rulebook"]["sha256"], "state": "read"}]
    files += [{"path": str(Path(assessment["folder"]) / d["file"]), "sha256": d.get("sha256"), "state": d["state"]}
              for d in assessment["documents"].values()]
    seen = assessment["payment"].get("reconcile") or {}
    if seen.get("path"):
        files.append({"path": seen["path"], "sha256": seen.get("sha256"),
                      "state": "read" if seen.get("exists") else "absent"})
    body = {key: value for key, value in assessment.items() if key not in ("packet", "packet_current")}
    content = {"renderer": RENDERER, "label": assessment["synthetic_label"], "mission_id": ctx.mission_id,
               "assessment": body,
               "previous": {"name": f"case-{_slug(assessment['reference'])}-"
                                    f"{previous['assessment']['assessment_digest'][7:23]}",
                            "assessment_digest": previous["assessment"]["assessment_digest"],
                            "receipt": previous_receipt} if previous else None,
               "changes": changes(previous["assessment"] if previous else None, body),
               "evidence_trail": {"files": files, "receipts": observed + ([previous_receipt] if previous_receipt else []),
                                  "request_events": [r["event_id"] for r in assessment["request"]["records"] or []]}}
    folder = Path(ctx.deliver_root).resolve() / "cases"
    folder.mkdir(parents=True, exist_ok=True)
    name = assessment["packet"]["name"]
    text, twin = render(content).encode("utf-8"), _json(content).encode("utf-8")
    delivered = _deliver(folder, name, {"packet.md": text, "packet.json": twin})
    return {"path": str(delivered / "packet.md"), "json_path": str(delivered / "packet.json"), "name": name,
            "assessment_digest": digest,
            "route": assessment["route"]["route"], "eligibility": assessment["eligibility"],
            "sha256": hashlib.sha256(text).hexdigest(), "json_sha256": hashlib.sha256(twin).hexdigest(),
            "packet": content}


def verify_delivery(output: dict, deliver_root: Path | None, ledger=None, *, confined: bool = False) -> tuple[bool, str]:
    """Appraiser: the delivered packet is the render of its receipted content, its assessment digest is the digest of
    that assessment, and both files are still on disk, byte for byte, inside the delivery root."""
    if not isinstance(output, dict) or not isinstance(output.get("packet"), dict):
        return False, "receipt does not retain the packet"
    content = output["packet"]
    if content.get("renderer") != RENDERER:
        return False, f"rendered by {content.get('renderer')}; this appraiser re-derives {RENDERER} only"
    assessment = dict(content.get("assessment") or {})
    digest = assessment.pop("assessment_digest", None)
    unshown = {k: v for k, v in assessment.items() if k not in ("complete", "decided")}
    if digest is None or assessment_digest(unshown) != digest:
        return False, "the packet's assessment digest is not the digest of its assessment"
    text, twin = render(content).encode("utf-8"), _json(content).encode("utf-8")
    if hashlib.sha256(text).hexdigest() != output.get("sha256") or hashlib.sha256(twin).hexdigest() != \
            output.get("json_sha256"):
        return False, "receipt digests are not the render of its packet"
    if deliver_root is None:
        return False, "this body has no delivery root"
    root = Path(deliver_root).resolve() / "cases"
    for key, data in (("path", text), ("json_path", twin)):
        path = Path(str(output.get(key)))
        if path.resolve().parent.parent != root or path.parent.name != output.get("name"):
            return False, f"the delivered {key} is outside the delivery root"
        if not path.is_file() or path.read_bytes() != data:
            return False, f"the delivered {path.name} differs from the render of its receipt"
    return True, "packet re-rendered from its receipt and found unchanged on disk"
