"""Capability acquisition for a blocked goal (directive section 15, Competency Compiler full horizon).

    goal -> active gate -> deficit -> search the repertoire -> inspect open-source mechanisms
         -> reuse or compose if sufficient -> qualify a supplied candidate -> founder attach decision
         -> register a bounded capability -> resume the ORIGINAL goal

What exists here, and what does not:

* ``plan`` walks the doctrine's resourcefulness ladder for an open deficit using only recorded facts:
  the router's rejection reasons for every registered mechanism (near misses), the router's exact
  composition search, and leads from the dated open-source catalog on ``main``
  (``docs/open-source/repositories-*.json``) matched by a declared method table. Leads are named as
  leads; nothing is downloaded, installed or run.
* ``qualify`` runs a candidate genome's own declared acceptance tests, plus any the caller adds (pytest
  node ids inside this repository's ``tests/`` tree only), in a subprocess with a timeout, under an evaluator identity that must differ
  from the candidate and from the acting agent. A subprocess is not an isolation boundary, and the
  record says so. Passing opens one founder decision; failing leaves the goal blocked.
* ``attach`` happens only after the founder accepts that decision: it refuses without the ledgered
  acceptance of the attach ask for that qualification, the genome is registered with an envelope capped
  at the goal's ceiling, the competency is registered with the router, and the capability starts
  unproven (CANARY). It earns calibration only from independently verified outcomes.
* ``sync`` replays attach and detach records, so an attached capability survives a restart and is
  routable by every loop on the ledger; replay writes nothing. An acceptance whose attach record was
  lost to a crash is completed on the next turn, never re-asked.
* ``detach`` removes a capability from routing at any time, with an accountable actor and a reason.
  The attachment stays on the ledger as history; replay never brings it back.
* No builder: GREG does not write the candidate's code. A person, a coding agent or another lineage
  (PR #129's genesis loop, PR #164's construction by reduction) supplies it; this module qualifies it.

Building != installation != activation != consequence authority. Attaching confers no grant.
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any, Mapping, Sequence

from capabilities.genome import CONSEQUENCE_CLASSES, AuthorityEnvelope, CapabilityGenome
from capabilities.router import EPISTEMIC_METHODS, HUMAN_ONLY_METHODS, PROBLEM_CLASSES, Competency

from .contracts import ContractError, canonical_copy, digest, require_text
from .goals import iso, parse_time
from .interventions import RESOLUTION_ORDER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE_ID = re.compile(r"^tests/[A-Za-z0-9_\-/]+\.py(::[A-Za-z0-9_\-\.\[\]]+)*$")

# Which catalogued open-source projects could plausibly supply which epistemic method. This table is an
# inference recorded for review, not a verified capability claim; a lead becomes a candidate only when
# someone wraps it as a genome with acceptance tests.
METHOD_LEADS: dict[str, tuple[str, ...]] = {
    "retrieval": ("searxng/searxng", "qdrant/qdrant", "huggingface/sentence-transformers", "microsoft/playwright"),
    "expert_judgment": ("ollama/ollama", "ggml-org/llama.cpp", "vllm-project/vllm", "mudler/LocalAI", "QwenLM/Qwen3"),
    "simulation": ("ollama/ollama", "ggml-org/llama.cpp"),
    "adversarial_review": ("ollama/ollama", "ggml-org/llama.cpp"),
    "empirical_experiment": ("n8n-io/n8n", "activepieces/activepieces"),
}
# Catalogued projects that are infrastructure (stores, search, workflow engines) rather than method suppliers.
INFRASTRUCTURE = frozenset({"qdrant/qdrant", "searxng/searxng", "temporalio/temporal", "n8n-io/n8n", "activepieces/activepieces"})


def _catalog() -> dict[str, Any]:
    paths = sorted(glob.glob(os.path.join(ROOT, "docs", "open-source", "repositories-*.json")))
    if not paths:
        return {"path": None, "observed_on": None, "evidence_type": None, "repositories": []}
    with open(paths[-1], encoding="utf-8") as fh:
        data = json.load(fh)
    return {"path": os.path.relpath(paths[-1], ROOT), "observed_on": data.get("observed_on"),
            "evidence_type": data.get("evidence_type"), "repositories": data.get("repositories", [])}


def _methods_needed(deficit: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    for m in deficit.get("missing_methods", []):
        if m.startswith("one of: "):
            out.extend(m[len("one of: "):].split("|"))
        elif m in EPISTEMIC_METHODS:
            out.append(m)
    return sorted(dict.fromkeys(out))


class CapabilityAcquisition:
    PLAN_RECORD = "egregore.acquisition_plan"
    QUALIFICATION_RECORD = "egregore.capability_qualification"
    ATTACH_RECORD = "egregore.capability_attached"
    DETACH_RECORD = "egregore.capability_detached"

    def __init__(self, loop: Any):
        self.loop = loop
        self._folded = 0
        self._attached: dict[str, dict[str, Any]] = {}   # qualification hash -> attach payload
        self._detached: set[str] = set()
        self._installed_genomes: set[str] = set()   # genomes this process installed through an attachment

    # ------------------------------------------------------------ fold
    def sync(self) -> None:
        """Replay attach and detach records appended since the last fold (an earlier process, another loop).

        A founder-attached capability is re-installed in the genome registry and the router without a new
        ledger event; a detached one is removed and never re-installed. The router does not restore
        competencies by itself, by design; the attach record is the evidence that this one was admitted."""
        records = self.loop.ledger.records
        start, self._folded = self._folded, len(records)
        for record in records[start:]:
            if record.record_type == self.ATTACH_RECORD:
                h = record.payload["qualification_hash"]
                self._attached[h] = record.payload
                if h not in self._detached:
                    self._install(record.payload, replay=True)
            elif record.record_type == self.DETACH_RECORD:
                h = record.payload["qualification_hash"]
                self._detached.add(h)
                if h in self._attached:
                    self._uninstall(self._attached[h])

    def _qualification(self, qualification_hash: str) -> dict[str, Any] | None:
        record = self.loop.ledger.find(qualification_hash)
        if record is None or record.record_type != self.QUALIFICATION_RECORD:
            return None
        return record.payload

    @staticmethod
    def _parts(q: Mapping[str, Any]) -> tuple[CapabilityGenome, Competency]:
        g = dict(q["candidate"]["genome"])
        genome = CapabilityGenome(authority=AuthorityEnvelope(**g.pop("authority")), **g)
        c = q["candidate"]["competency"]
        return genome, Competency(c["genome_name"], c["genome_version"], tuple(c["methods"]), tuple(c["problem_classes"]),
                                  c["consequence_class"], c["cost_usd"])

    def _same_as_registered(self, genome: CapabilityGenome) -> None:
        """The founder is shown the candidate's envelope, so a different genome already registered under the same
        name@version (for example a wider envelope) is refused rather than silently attached."""
        existing = self.loop.genomes.get(genome.name, genome.version) if self.loop.genomes is not None else None
        if existing is not None and existing != genome:
            raise ContractError(f"a different genome is already registered as {genome.name}@{genome.version}; "
                                "qualify a new version instead")

    def _install(self, attach: Mapping[str, Any], *, replay: bool) -> tuple[bool, bool]:
        q = self._qualification(attach["qualification_hash"])
        if q is None or self.loop.genomes is None:
            if not replay:
                raise ContractError("attaching needs the qualification on the ledger and a genome registry")
            return False, False
        genome, competency = self._parts(q)
        existing = self.loop.genomes.get(genome.name, genome.version)
        if existing is not None and existing != genome:
            if replay:
                return False, False   # never route an attachment through a genome other than the one qualified
            raise ContractError(f"a different genome is already registered as {genome.name}@{genome.version}")
        genome_registered = False
        if self.loop.genomes.get(genome.name, genome.version) is None:
            if replay:
                if genome.validate():
                    return False, False   # a malformed historical record is evidence, not a registration
                self.loop.genomes._genomes[f"{genome.name}@{genome.version}"] = genome   # replay, no new ledger event
            else:
                self.loop.genomes.register(genome)
            genome_registered = True
            self._installed_genomes.add(f"{genome.name}@{genome.version}")
        competency_registered = False
        if self.loop.competency is not None:
            if replay:
                competency_registered = self.loop.competency.replay(competency)
            else:
                self.loop.competency.register(competency)
                competency_registered = True
        return genome_registered, competency_registered

    def _uninstall(self, attach: Mapping[str, Any]) -> None:
        key = attach["candidate_key"]
        if self.loop.competency is not None:
            self.loop.competency.retire(key)
        if key in self._installed_genomes and self.loop.genomes is not None:   # never remove someone else's genome
            self.loop.genomes._genomes.pop(key, None)
            self._installed_genomes.discard(key)

    def _accepted_answer(self, qualification_hash: str, goal_id: str) -> Any:
        """The founder's ledgered acceptance of the attach ask for this qualification, or None."""
        attention = self.loop.attention
        items = {r.payload["item"]["item_id"] for r in self.loop.ledger.by_type(attention.ASK_RECORD)
                 if (r.payload["item"].get("attach_on_accept") or {}).get("qualification_hash") == qualification_hash
                 and r.payload["item"].get("goal_id") == goal_id}
        return next((r for r in self.loop.ledger.by_type(attention.ANSWER_RECORD)
                     if r.payload["item_id"] in items and r.payload["decision"] == "accept"), None)

    @property
    def execution_authority(self) -> str:
        return "none"

    # ------------------------------------------------------------ open deficits
    def open_deficits(self, goal_id: str) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for r in self.loop.ledger.by_type(self.loop.classifier.DEFICIT_RECORD):
            d = r.payload.get("deficit") or {}
            if d.get("goal_id") == goal_id:
                latest[d["deficit_id"]] = d
        return [d for d in latest.values() if d["disposition"] == "goal_blocked_not_closed"]

    # ------------------------------------------------------------ plan
    def plan(self, goal_id: str, *, now: datetime | str) -> dict[str, Any]:
        at = iso(parse_time(now))
        spec = self.loop.registry.get(goal_id)
        deficits = self.open_deficits(goal_id)
        if not deficits:
            raise ContractError("no open deficit for this goal; nothing to acquire")
        deficit = deficits[-1]
        methods = _methods_needed(deficit)
        catalog = _catalog()
        known = {r["repo"]: r for r in catalog["repositories"]}
        leads = [{"repo": repo, "method": m, "license": known[repo].get("license"), "archived": known[repo].get("archived"),
                  "pushed_at": known[repo].get("pushed_at"), "status": "lead: unverified, not installed"}
                 for m in methods for repo in METHOD_LEADS.get(m, ()) if repo in known]
        unwrapped = []
        if self.loop.competency is not None:
            competent = set(self.loop.competency.router._competencies)
            unwrapped = sorted(k for k in self.loop.genomes._genomes if k not in competent)
        rungs = []
        for rung in RESOLUTION_ORDER:
            if rung == "existing capability":
                finding = {"near_misses": dict(deficit.get("rejected", {})), "registered_without_competency": unwrapped}
            elif rung.startswith("composition"):
                finding = {"searched": bool(deficit.get("missing_methods")),
                           "result": "the router searched every exact cover within the gate's budget; none answers"
                                     if deficit.get("missing_methods") else "not applicable to a declared capability"}
            elif rung in ("commodity infrastructure", "open source"):
                finding = {"catalog": catalog["path"], "observed_on": catalog["observed_on"],
                           "catalog_evidence": catalog["evidence_type"],
                           "leads": [l for l in leads if (l["repo"] in INFRASTRUCTURE) == (rung == "commodity infrastructure")]}
            elif rung == "escalate/abstain":
                finding = {"note": "if no candidate qualifies, the goal stays blocked and Alfonso decides"}
            else:
                finding = {"status": "needs a supplier (person, coding agent, or another lineage) to propose a candidate "
                                     "genome with acceptance tests; GREG qualifies, it does not build"}
            rungs.append({"rung": rung, "finding": finding})
        plan = {"source": self.loop.source, "plan_id": digest({"kind": "egregore-acquisition-plan", "goal_id": goal_id,
                                                                 "deficit_id": deficit["deficit_id"]}),
                "goal_id": goal_id, "deficit_id": deficit["deficit_id"], "methods_needed": methods,
                "missing_capabilities": list(deficit.get("missing_capabilities", [])), "rungs": rungs,
                "planned_at": at, "founder_intent": spec.founder_intent,
                "disposition": "prepared_not_executed: no download, install, build or activation"}
        if not any(r.payload["plan_id"] == plan["plan_id"] for r in self.loop.ledger.by_type(self.PLAN_RECORD)):
            self.loop.ledger.append(self.PLAN_RECORD, canonical_copy(plan))
        return plan

    # ------------------------------------------------------------ qualify
    @staticmethod
    def _check_nodes(nodes: Sequence[str]) -> list[str]:
        clean = []
        for node in nodes:
            node = require_text("acceptance test", node)
            if ".." in node or not NODE_ID.match(node):
                raise ContractError(f"acceptance tests must be pytest node ids inside tests/: {node!r}")
            if not os.path.isfile(os.path.join(ROOT, node.split("::", 1)[0])):
                raise ContractError(f"acceptance test file does not exist: {node!r}")
            clean.append(node)
        if not clean:
            raise ContractError("a candidate needs at least one acceptance test")
        return clean

    def qualify(self, goal_id: str, *, genome: CapabilityGenome, competency: Competency, acceptance_tests: Sequence[str],
                evaluator: str, now: datetime | str, timeout_seconds: int = 300) -> dict[str, Any]:
        at = iso(parse_time(now))
        spec = self.loop.registry.get(goal_id)
        evaluator = require_text("evaluator", evaluator)
        def identity(value: Any) -> str:   # "x@anything" is still x
            return str(value or "").split("@", 1)[0].strip().casefold()
        if identity(evaluator) in {identity(self.loop.classifier.actor), identity(self.loop.source), identity(genome.name)}:
            raise ContractError("the evaluator must be independent of the candidate and of the acting agent")
        problems = genome.validate()
        if problems:
            raise ContractError(f"candidate genome is invalid: {problems}")
        if (competency.genome_name, competency.genome_version) != (genome.name, genome.version):
            raise ContractError("the competency must describe the candidate genome")
        if set(competency.methods) & HUMAN_ONLY_METHODS or not set(competency.methods) <= set(EPISTEMIC_METHODS):
            raise ContractError("a candidate may claim only machine epistemic methods")
        if not set(competency.problem_classes) <= set(PROBLEM_CLASSES):
            raise ContractError("unknown problem class in the candidate's competency")
        ceiling = spec.authority["max_consequence_class"]
        if CONSEQUENCE_CLASSES.index(genome.authority.max_consequence_class) > CONSEQUENCE_CLASSES.index(ceiling):
            raise ContractError(f"candidate envelope {genome.authority.max_consequence_class} exceeds the goal ceiling {ceiling}")
        if competency.consequence_class not in CONSEQUENCE_CLASSES or (
                CONSEQUENCE_CLASSES.index(competency.consequence_class)
                > CONSEQUENCE_CLASSES.index(genome.authority.max_consequence_class)):
            raise ContractError(f"the competency's class {competency.consequence_class} exceeds the candidate envelope "
                                f"{genome.authority.max_consequence_class}")
        self._same_as_registered(genome)
        # The candidate's own declared acceptance tests always run (and must be runnable node ids); the caller may
        # add tests, never substitute them, so "passed its acceptance tests" means the tests the genome declares.
        nodes = self._check_nodes(list(dict.fromkeys(list(genome.acceptance_tests) + list(acceptance_tests))))
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *nodes]
        env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL", "PYTHONPATH", "TMPDIR")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        try:
            run = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout_seconds)
            code, out = run.returncode, (run.stdout + run.stderr)
        except subprocess.TimeoutExpired as exc:
            code, out = -1, f"timeout after {timeout_seconds}s: {exc}"
        passed = code == 0
        tail = out.strip().splitlines()[-1] if out.strip() else ""
        candidate = {"genome": {**genome.__dict__, "authority": genome.authority.__dict__},
                     "competency": {"genome_name": competency.genome_name, "genome_version": competency.genome_version,
                                    "methods": list(competency.methods), "problem_classes": list(competency.problem_classes),
                                    "consequence_class": competency.consequence_class, "cost_usd": competency.cost_usd}}
        record = {"source": self.loop.source, "goal_id": goal_id, "candidate_key": f"{genome.name}@{genome.version}",
                  "candidate": canonical_copy(candidate), "acceptance_tests": nodes, "evaluator": evaluator,
                  "exit_code": code, "passed": passed, "summary": tail[:300],
                  "output_digest": digest({"kind": "egregore-qualification-output", "output": out}),
                  "lifecycle": "TESTED" if passed else "QUARANTINED", "qualified_at": at,
                  "isolation": "subprocess with a timeout inside this repository; not an isolation boundary",
                  "disposition": "qualified; awaiting founder attach decision" if passed else "failed; goal stays blocked"}
        appended = self.loop.ledger.append(self.QUALIFICATION_RECORD, canonical_copy(record))
        record["qualification_hash"] = appended.hash
        return record

    def attach_item(self, goal_id: str, qualification: Mapping[str, Any], *, now: str) -> Any:
        """One founder decision: attach the qualified candidate (records only; attach happens on accept)."""
        from .attention import AttentionItem
        spec = self.loop.registry.get(goal_id)
        comp = qualification["candidate"]["competency"]
        env = qualification["candidate"]["genome"]["authority"]
        return AttentionItem.build(
            goal_id=goal_id, kind="decision", urgency="normal", marginal_value=0.8,
            title=f"{spec.desired_state[:60]}: attach {qualification['candidate_key']}",
            question=(f"Candidate {qualification['candidate_key']} passed {len(qualification['acceptance_tests'])} acceptance "
                      f"test(s) run by {qualification['evaluator']} ({qualification['isolation']}). Attaching makes it routable "
                      f"for {', '.join(comp['problem_classes'])} via {', '.join(comp['methods'])} inside envelope "
                      f"{env['max_consequence_class']}. It starts unproven and earns a track record only from independently "
                      f"verified outcomes. Attaching is not a grant and executes nothing."),
            options=({"label": "accept (attach)", "cost": "one decision"}, {"label": "refuse", "cost": "none"},
                     {"label": "do nothing now", "cost": "none"}),
            recommendation="attach if the acceptance tests cover what the gate needs",
            evidence_refs=(qualification["qualification_hash"],), effort_estimate="one decision",
            category="capability_attach", created_at=now,
            attach_on_accept={"qualification_hash": qualification["qualification_hash"], "goal_id": goal_id})

    # ------------------------------------------------------------ attach
    def attach(self, qualification_hash: str, *, actor: str, now: datetime | str) -> dict[str, Any]:
        """Attach a qualified candidate the founder accepted. Refused without that ledgered acceptance."""
        at = iso(parse_time(now))
        self.loop.attention.sync()
        self.sync()
        q = self._qualification(qualification_hash)
        if q is None or not q.get("passed"):
            raise ContractError("only a passed qualification on the ledger can be attached")
        if qualification_hash in self._attached:
            raise ContractError("this qualification is already attached")
        answer = self._accepted_answer(qualification_hash, q["goal_id"])
        if answer is None:
            raise ContractError("attach requires the founder's accepted answer to the attach decision for this qualification")
        actor = require_text("actor", actor)
        if actor != answer.payload["actor"]:
            raise ContractError("the attaching actor must be the one who accepted the attach decision")
        genome_registered, registered_competency = self._install({"qualification_hash": qualification_hash}, replay=False)
        key = q["candidate_key"]
        if self.loop.retention is not None:   # declared capability deficits naming this genome resume their goal
            self.loop.retention._resolve_deficits(q["goal_id"], [key], retained_at=at, resolved_by=f"attach:{key}")
        attach = {"source": self.loop.source, "goal_id": q["goal_id"], "qualification_hash": qualification_hash,
                  "candidate_key": key, "attached_by": actor, "answer_hash": answer.hash, "attached_at": at,
                  "genome_registered": genome_registered, "competency_registered": registered_competency,
                  "lifecycle": "CANARY", "authority_note": "attached on a founder decision; not a grant; starts unproven",
                  "disposition": "attached; the original goal resumes when its gate routes"}
        self.loop.ledger.append(self.ATTACH_RECORD, canonical_copy(attach))
        self._attached[qualification_hash] = attach
        self._folded = len(self.loop.ledger.records)
        return attach

    def complete_accepted(self, *, now: datetime | str) -> list[dict[str, Any]]:
        """Finish attaches the founder accepted but whose attach record never landed (a crash between the answer
        and the attach). The acceptance is the decision; it is never asked again."""
        self.loop.attention.sync()
        self.sync()
        done = []
        for r in self.loop.ledger.by_type(self.loop.attention.ASK_RECORD):
            attach = r.payload["item"].get("attach_on_accept") or {}
            h = attach.get("qualification_hash")
            if not h or h in self._attached or h in self._detached:
                continue
            q = self._qualification(h)
            answer = self._accepted_answer(h, attach.get("goal_id")) if q and q.get("passed") else None
            if answer is not None:
                done.append(self.attach(h, actor=answer.payload["actor"], now=now))
        return done

    def detach(self, qualification_hash: str, *, actor: str, reason: str, now: datetime | str) -> dict[str, Any]:
        """Remove an attached capability from routing. Reducing capability needs no grant; it needs an
        accountable actor and a reason. The ledger keeps the attachment as history."""
        at = iso(parse_time(now))
        self.sync()
        attach = self._attached.get(qualification_hash)
        if attach is None:
            raise ContractError("only an attached capability can be detached")
        if qualification_hash in self._detached:
            raise ContractError("this capability is already detached")
        record = {"source": self.loop.source, "goal_id": attach["goal_id"], "qualification_hash": qualification_hash,
                  "candidate_key": attach["candidate_key"], "detached_by": require_text("actor", actor),
                  "reason": require_text("reason", reason), "detached_at": at, "lifecycle": "HISTORICAL",
                  "disposition": "detached; not routable; preserved on the ledger and never replayed"}
        self.loop.ledger.append(self.DETACH_RECORD, canonical_copy(record))   # ledger first, then the effect
        self._detached.add(qualification_hash)
        self._uninstall(attach)
        self._folded = len(self.loop.ledger.records)
        return record
