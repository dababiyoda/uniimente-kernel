"""#1 Declarative compiler: source documents -> typed, hashed draft objects.

One front end (YAML with position tracking) and one back end per ``kind``:

  workflow        explicitly allowed Foundry operations -> a reviewable plan
  policy          named DSL rules -> parsed rule set #2 evaluates
  experiment      hypothesis, metric, falsifier, stop rule, budget -> a test plan
  business        a Business Genome -> validated by business/genome.py (its single owner)
  organ_charter   capabilities with typed contracts -> an unregistered descriptor
  swarm_contract  a bounded team: members, grants, objective, dissolution -> a team spec (#48)

Every error is located (``file:line:col: message``) and reported before anything
executes; an invalid document compiles to nothing. Compilation grants no authority
and activates no policy, workflow, team, charter or business. Output is canonical JSON, so
the same source always yields the same hash. The UCL constitutional compiler
(compiler/ucl_compiler.py) keeps compiling the constitution itself.
"""
from __future__ import annotations

import hashlib
import json

import yaml

from capabilities.genome import CONSEQUENCE_CLASSES


class CompileError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def _positions(node, path=(), out=None) -> dict:
    out = {} if out is None else out
    out[path] = (node.start_mark.line + 1, node.start_mark.column + 1)
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            out[path + (k.value,)] = (k.start_mark.line + 1, k.start_mark.column + 1)
            _positions(v, path + (k.value,), out)
    elif isinstance(node, yaml.SequenceNode):
        for i, v in enumerate(node.value):
            _positions(v, path + (i,), out)
    return out


class _Ctx:
    def __init__(self, filename, positions):
        self.filename, self.positions, self.problems = filename, positions, []

    def err(self, path: tuple, message: str) -> None:
        p = tuple(path)
        while p not in self.positions and p:
            p = p[:-1]
        line, col = self.positions.get(p, (1, 1))
        self.problems.append(f"{self.filename}:{line}:{col}: {message}")

    def need(self, doc: dict, path: tuple, fields: tuple) -> None:
        for f in fields:
            if doc.get(f) in (None, "", [], {}):
                self.err(path + (f,) if f in doc else path, f"missing required field {f!r}")


def _workflow(doc, c):
    from greg.foundry_bridge import operation_class
    c.need(doc, (), ("id", "steps"))
    names = set()
    for i, s in enumerate(doc.get("steps") or []):
        at = ("steps", i)
        if s.get("name") in names:
            c.err(at + ("name",), f"duplicate step name {s.get('name')!r}")
        names.add(s.get("name"))
        try:
            cls = operation_class(s["system"], s["op"])
        except (KeyError, TypeError, ValueError) as exc:
            c.err(at, f"step {s.get('name')!r}: {exc}")
            continue
        if cls == "internal_write" and not s.get("write"):
            c.err(at + ("op",), f"step {s.get('name')!r} writes ({s['op']}) and must declare write: true")
        if cls == "read_only" and s.get("write"):
            c.err(at + ("write",), f"step {s.get('name')!r} declares write for a read-only op")
    return {"workflow_id": doc.get("id"), "steps": doc.get("steps")}


def _policy(doc, c):
    from foundry.systems import dsl
    c.need(doc, (), ("id", "language", "rules"))
    for name, source in (doc.get("rules") or {}).items():
        try:
            dsl.parse(doc.get("language"), source)
        except dsl.RuleError as exc:
            c.err(("rules", name), f"rule {name!r}: {exc}")
    return {"policy_id": doc.get("id"), "language": doc.get("language"), "rules": doc.get("rules")}


def _experiment(doc, c):
    from foundry.systems.observability import METRICS
    c.need(doc, (), ("id", "hypothesis", "metric", "falsifier", "stop_rule", "budget_usd"))
    if doc.get("metric") and doc["metric"] not in METRICS and not str(doc["metric"]).startswith("custom:"):
        c.err(("metric",), f"unknown metric {doc['metric']!r}; measured metrics are {list(METRICS)} or custom:<name>")
    if isinstance(doc.get("budget_usd"), (int, float)) and doc["budget_usd"] < 0:
        c.err(("budget_usd",), "budget may not be negative")
    if doc.get("falsifier") and doc.get("falsifier") == doc.get("hypothesis"):
        c.err(("falsifier",), "a falsifier that restates the hypothesis cannot fail")
    return {k: doc.get(k) for k in ("id", "hypothesis", "metric", "falsifier", "stop_rule", "budget_usd")}


_PROBLEM_FIELDS = (("does not cover marginal cost", "price_usd"), ("price must", "price_usd"),
                   ("marginal cost may", "marginal_cost_usd"), ("demand evidence", "demand_evidence_refs"),
                   ("required capabilities", "required_capabilities"), ("may never do", "legal_restrictions"),
                   ("legal operator", "legal_operator"), ("genome missing ", None))


def _business(doc, c):
    from business.genome import BusinessGenome
    fields = BusinessGenome.__dataclass_fields__
    unknown = sorted(set(doc) - set(fields) - {"kind"})
    for u in unknown:
        c.err((u,), f"unknown genome field {u!r}")
    from dataclasses import MISSING
    missing = [f for f, spec in fields.items() if f not in doc and spec.default is MISSING and spec.default_factory is MISSING]
    for m in missing:
        c.err((), f"missing genome field {m!r}")
    if unknown or missing:
        return None
    g = BusinessGenome(**{k: v for k, v in doc.items() if k != "kind"})
    g.required_capabilities = [tuple(x) for x in g.required_capabilities]
    for problem in g.validate():
        field = next((f for key, f in _PROBLEM_FIELDS if key in problem), None)
        if problem.startswith("genome missing "):
            field = problem.removeprefix("genome missing ")
        c.err((field,) if field else (), problem)
    return {"genome": {k: doc[k] for k in sorted(doc) if k != "kind"}, "genome_hash": g.hash()}


def _organ_charter(doc, c):
    from linker.linker import known_contracts
    c.need(doc, (), ("organ_id", "capabilities", "prohibited_actions"))
    contracts = set(known_contracts())
    for i, cap in enumerate(doc.get("capabilities") or []):
        for side in ("consumes", "produces"):
            for j, name in enumerate(cap.get(side, [])):
                if name not in contracts:
                    c.err(("capabilities", i, side, j), f"untyped contract {name!r} (no contracts/{name}.schema.json)")
        if cap.get("consequence_class") not in CONSEQUENCE_CLASSES:
            c.err(("capabilities", i, "consequence_class"), f"unknown consequence class {cap.get('consequence_class')!r}")
    caps = doc.get("capabilities") or []
    return {"descriptor": {"organ_id": doc.get("organ_id"), "capabilities": [
                {"capability_id": x.get("capability_id"), "consumes": x.get("consumes", []), "produces": x.get("produces", []),
                 "consequence_class": x.get("consequence_class"), "health": "unknown", "cost_usd": None,
                 "latency_ms": None} for x in caps]},
            "prohibited_actions": doc.get("prohibited_actions")}


def _swarm_contract(doc, c):
    c.need(doc, (), ("id", "objective", "members", "dissolve_on", "budget_usd"))
    roles = set()
    for i, m in enumerate(doc.get("members") or []):
        if m.get("role") in roles:
            c.err(("members", i, "role"), f"duplicate role {m.get('role')!r}")
        roles.add(m.get("role"))
        if not m.get("capabilities"):
            c.err(("members", i), f"member {m.get('role')!r} declares no capabilities")
        if m.get("max_consequence") not in CONSEQUENCE_CLASSES:
            c.err(("members", i, "max_consequence"), f"unknown consequence class {m.get('max_consequence')!r}")
    return {k: doc.get(k) for k in ("id", "objective", "members", "dissolve_on", "budget_usd")}


BACKENDS = {"workflow": _workflow, "policy": _policy, "experiment": _experiment, "business": _business,
            "organ_charter": _organ_charter, "swarm_contract": _swarm_contract}


def compile_source(text: str, filename: str = "<source>") -> dict:
    if not isinstance(text, str) or len(text.encode()) > 32768:
        raise CompileError([f"{filename}:1:1: source exceeds the 32 KiB ceiling"])
    try:
        # Anchors/aliases can produce recursive or exponentially reused objects.
        # The restricted draft language needs neither.
        if any(isinstance(t, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)) for t in yaml.scan(text)):
            raise CompileError([f"{filename}:1:1: YAML anchors and aliases are unsupported"])
        node = yaml.compose(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"{mark.line + 1}:{mark.column + 1}" if mark else "1:1"
        raise CompileError([f"{filename}:{where}: syntax: {getattr(exc, 'problem', exc)}"]) from None
    if node is None or not isinstance(node, yaml.MappingNode):
        raise CompileError([f"{filename}:1:1: a source document must be a mapping"])
    doc = yaml.safe_load(text)
    def bounded(value, depth=0):
        if depth > 16:
            raise CompileError([f"{filename}:1:1: nesting ceiling exceeded"])
        if isinstance(value, dict):
            if len(value) > 128 or any(not isinstance(k, str) for k in value):
                raise CompileError([f"{filename}:1:1: mappings need bounded string keys"])
            for v in value.values():
                bounded(v, depth + 1)
        elif isinstance(value, list):
            if len(value) > 128:
                raise CompileError([f"{filename}:1:1: sequence ceiling exceeded"])
            for v in value:
                bounded(v, depth + 1)
        elif value is not None and not isinstance(value, (str, int, float, bool)):
            raise CompileError([f"{filename}:1:1: unsupported YAML scalar"])
    bounded(doc)
    c = _Ctx(filename, _positions(node))
    kind = doc.get("kind")
    if kind not in BACKENDS:
        c.err(("kind",), f"unknown kind {kind!r}; kinds are {sorted(BACKENDS)}")
        raise CompileError(c.problems)
    body = BACKENDS[kind](doc, c)
    if c.problems:
        raise CompileError(c.problems)
    obj = {"kind": kind, "object": body, "authority_created": False,
           "execution_state": "DECLARATIVE_DRAFT", "world_validity": "UNVERIFIED"}
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return {**obj, "hash": "sha256:" + hashlib.sha256(canonical.encode()).hexdigest(),
            "source_hash": "sha256:" + hashlib.sha256(text.encode()).hexdigest()}


def _check(args):
    try:
        return {"ok": True, "compiled": compile_source(args["source"], args.get("filename", "<source>"))}
    except CompileError as exc:
        return {"ok": False, "errors": exc.problems}


QUERY_OPS = {"compile": lambda a, r: _check(a)}
APPLY_OPS: dict = {}  # Existing fs.write / artifact.store own persistence.


SOURCES = {
    "workflow.yaml": """kind: workflow
id: store-and-verify
steps:
  - name: store
    system: 2
    op: run
    args: {language: pricing, source: base_price * units, inputs: {base_price: 10, units: 2}}
  - name: verify
    system: 43
    op: check_approval_boundary
""",
    "policy.yaml": """kind: policy
id: quote-pricing
language: pricing
rules:
  list: base_price * units
  floor: max(base_price * units * 0.9, cost_per_unit * units * 1.2)
""",
    "experiment.yaml": """kind: experiment
id: proof-sells
hypothesis: buyers pay more for verified outcomes
metric: verified_rate
falsifier: fewer than 2 of 10 buyers accept the proof-priced offer
stop_rule: 10 offers or 14 days
budget_usd: 0
""",
    "business.yaml": """kind: business
name: proof-rail-audit
problem: suppliers cannot prove delivery to buyers
buyer: procurement lead at a mid-size distributor
offer: verified delivery audit
price_usd: 900
distribution: owned newsletter
conversion: audit call
fulfillment: GREG evidence pack
retention: monthly re-audit
marginal_cost_usd: 120
demand_evidence_refs: ["interview:2026-09-20:a"]
required_capabilities: [["evidence-pack", "1.0"]]
required_workflows: []
legal_restrictions: ["no payment custody"]
regenerative_effect: suppliers become eligible for faster payment
kill_condition: fewer than 2 paid audits in 90 days
falsification_test: 10 offers, 2 paid
""",
    "charter.yaml": """kind: organ_charter
organ_id: organ:wmi
capabilities:
  - capability_id: wmi.assess
    consumes: [wire-opportunity-packet]
    produces: [wire-venture-assessment]
    consequence_class: read_only
prohibited_actions: [spend, publish]
""",
    "swarm.yaml": """kind: swarm_contract
id: offer-sprint
objective: draft and price one offer from interview evidence
budget_usd: 0
dissolve_on: offer drafted or 2 days
members:
  - role: analyst
    capabilities: [foundry.query]
    max_consequence: read_only
  - role: writer
    capabilities: [foundry.query, foundry.apply]
    max_consequence: internal_write
""",
}

BROKEN = {
    "workflow-bad.yaml": SOURCES["workflow.yaml"].replace("    system: 2", "    system: 12"),
    "policy-bad.yaml": SOURCES["policy.yaml"].replace("cost_per_unit * units * 1.2", "__import__('os')"),
    "business-bad.yaml": SOURCES["business.yaml"].replace("price_usd: 900", "price_usd: 100"),
    "charter-bad.yaml": SOURCES["charter.yaml"].replace("[wire-venture-assessment]", "[made-up-contract]"),
    "syntax-bad.yaml": "kind: policy\nrules: [unclosed\n",
    "experiment-bad.yaml": SOURCES["experiment.yaml"].replace(
        "falsifier: fewer than 2 of 10 buyers accept the proof-priced offer", "falsifier: buyers pay more for verified outcomes"),
}


def exercise(root) -> dict:
    compiled = {name: compile_source(text, name) for name, text in SOURCES.items()}
    again = {name: compile_source(text, name)["hash"] for name, text in SOURCES.items()}
    errors = {}
    for name, text in BROKEN.items():
        try:
            compile_source(text, name)
            errors[name] = None
        except CompileError as exc:
            errors[name] = exc.problems
    return {"kinds": sorted(c["kind"] for c in compiled.values()),
            "deterministic": all(compiled[n]["hash"] == again[n] for n in SOURCES),
            "hashes": {n: c["hash"][:23] for n, c in compiled.items()},
            "located_errors": errors, "drafts_only": all(c["execution_state"] == "DECLARATIVE_DRAFT" for c in compiled.values()),
            "authority_created": False}
