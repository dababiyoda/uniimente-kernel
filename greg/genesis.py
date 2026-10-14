"""Capability Genesis: canonical UNIIMENTE morphogenesis as a working mechanism.

When a mission needs a function GREG does not have, it does not stop and it does
not pretend. It opens a CapabilityDeficit, freezes the acceptance test *before*
any candidate exists, then searches reality in resourcefulness order:

    1. an ATTACHED capability with that function            (use what exists)
    2. a VERIFIED, never explicitly detached capability     (attach in signed scope)
    3. installed commodity software on this body            (acquire)
       - an executable, or
       - an installed open-source package (DEPEND, greg/mechanisms.py): Mechanism Card
         with version, license, upstream and file digest; GREG's certificate checks
         every answer it gives
    4. a pluggable builder (coding agent / human / model)   (build the residual)
    5. founder escalation                                   (ask, wait)

Every candidate is untrusted. It runs with no network, a scrubbed environment and
a timeout, and is judged by an independent oracle that the candidate never sees.
A passing candidate is registered with provenance (binary path and content hash,
version string, builder identity) as VERIFIED. Attachment still needs either a
founder CAPABILITY_ATTACH command or a founder-signed mission ``auto_attach``
limited to read-only functions. The original mission then resumes; genesis
completion never closes the mission.

An explicit founder DETACHED identity is skipped by automatic discovery,
including when installed software or a builder returns that identity again.
A different independently verified provider can still serve the function.

Self-repair: a formed capability that later fails in service (its built source or
binary changed, or it raises on live input) is quarantined with the failure as
evidence, and the same search runs again as a new deficit generation. A rebuilt
candidate must pass the same frozen oracle *and* run cleanly on the live input
that broke its predecessor (replayed locally in isolation; never sent to a model).

Cognition deficits (directive 2026-10-07 section 24; section 31 item 14): when the
Competency Compiler finds no method for a geometry it reports ``cognition.<class>:<sub>``
with the inputs the request carries. Genesis then searches, simplest first:

    1. an ATTACHED capability with that function
    2. the registered repertoire (catalog families and the executable genome library) for
       a family whose native class and inputs fit; a registered, withheld one is reported
       as an attach candidate under frozen admission evidence, never attached
    3. installed open-source mechanisms whose declared geometry serves the residual
       (``signature``), qualified like any package: Mechanism Card, frozen oracle drawn from
       admission instance generators on development seeds only, GREG's certificate
    4. a builder against a founder-signed contract, then the founder

Nothing found for a cognition deficit is ever attached by GREG, not even under a
mission's ``auto_attach``: the mission engine records one founder ask (greg/asks.py)
naming the candidates. After the founder's attach, the compiler routes the geometry to
the formed mechanism and accepts each answer only on GREG's certificate.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import random
import stat
import sys
import tempfile
import time

from greg.capabilities import (CapabilityError, CapabilityManifest, InvocationContext, installed_binary,
                               run_isolated)
from greg.artifacts import ArtifactStore
from greg import builders, mechanisms
from greg.cognition import assignment, linear, network
from greg.journal import Journal, iso
from greg.mechanisms import PackageCandidate
from provenance.ledger import sha256_json


# -- frozen acceptance oracles ------------------------------------------------------
# An oracle produces test vectors and judges outputs. It is written before any
# candidate is searched and is never passed to a candidate.

def _vectors_hash(seed: int):
    rng = random.Random(seed)
    cases = []
    for index in range(6):
        size = rng.choice([0, 1, 17, 1024, 65537, rng.randint(2, 5000)])
        data = bytes(rng.getrandbits(8) for _ in range(size))
        cases.append({"name": f"case{index}.bin", "data": data,
                      "expected": hashlib.sha256(data).hexdigest()})
    return cases


def _vectors_wordcount(seed: int):
    rng = random.Random(seed)
    words = ["alpha", "beta", "gamma", "delta", "ñandú", "egregore", "x"]
    cases = []
    for index in range(6):
        text = "\n".join(" ".join(rng.choice(words) for _ in range(rng.randint(0, 12)))
                         for _ in range(rng.randint(0, 6)))
        cases.append({"name": f"case{index}.txt", "data": text.encode(), "expected": len(text.split())})
    return cases


@dataclass(frozen=True)
class Candidate:
    """How one installed tool realizes a function: argv template and output parser."""
    binary_name: str
    argv: tuple                        # tokens; "{binary}" and "{file}" are substituted
    parse: str                         # parser id below


PARSERS = {
    "first_hex_token": lambda out: out.split()[0].lower() if out.split() else "",
    "last_hex_token": lambda out: out.strip().split()[-1].lower() if out.split() else "",
    "first_int": lambda out: int(out.split()[0]) if out.split() else -1,
}

CATALOG = {
    "hash.sha256": {
        "description": "SHA-256 digest of one file",
        "oracle": _vectors_hash, "output_field": "sha256",
        "candidates": (Candidate("sha256sum", ("{binary}", "--", "{file}"), "first_hex_token"),
                       Candidate("shasum", ("{binary}", "-a", "256", "{file}"), "first_hex_token"),
                       Candidate("openssl", ("{binary}", "dgst", "-sha256", "{file}"), "last_hex_token")),
    },
    "text.wordcount": {
        "description": "Whitespace-separated word count of one text file",
        "oracle": _vectors_wordcount, "output_field": "words",
        "candidates": (Candidate("wc", ("{binary}", "-w", "{file}"), "first_int"),),
    },
    # Open-source packages (founder correction 2026-10-01, #144): installed engines, never installed by GREG.
    "graph.shortest_path": {
        "kind": "package", "description": "Every shortest distance from a source over nonnegative weights, and the "
                                          "path to an optional target, with an optimality certificate",
        "oracle": network.oracle_shortest, "oracle_kind": "Bellman-Ford in exact fractions (GREG)",
        "output_field": "certified", "normalize": network.normalize_shortest, "certify": network.certify_shortest,
        "judge": network.judge_shortest, "probe": network.probe_shortest, "size": network.size,
        "baseline": ("local binary-heap Dijkstra (plain Python)", network.local_dijkstra, "distances"),
        "project": [("cognition.graph", "PR #140 op: one s-t path, checked for validity but not optimality; no "
                                        "distances or unreachability certificate")],
        "candidates": (
            PackageCandidate("networkx", "networkx", "networkx.shortest_path",
                             ("networkx/__init__.py", "networkx/classes/", "networkx/algorithms/shortest_paths/",
                              "networkx/utils/", "networkx/exception.py"),
                             "Dijkstra with predecessor lists (networkx.dijkstra_predecessor_and_distance)",
                             "nonnegative finite weights; GREG keeps the lightest of parallel edges"),
            PackageCandidate("scipy", "scipy.sparse.csgraph", "scipy.shortest_path",
                             ("scipy/__init__.py", "scipy/sparse/csgraph/"),
                             "compiled Dijkstra on a sparse matrix (scipy.sparse.csgraph.dijkstra)",
                             "nonnegative finite weights in float64; GREG keeps the lightest of parallel edges, "
                             "since the sparse matrix would sum them", ("numpy",))),
    },
    "graph.max_flow": {
        "kind": "package", "description": "Maximum flow from a source to a sink over integer arc capacities, with a "
                                          "minimum cut as its certificate",
        "oracle": network.oracle_max_flow, "oracle_kind": "brute-force minimum cut over every source side (GREG)",
        "output_field": "certified", "normalize": network.normalize_max_flow, "certify": network.certify_max_flow,
        "judge": network.judge_max_flow, "probe": network.probe_max_flow, "size": network.size,
        "baseline": ("local Edmonds-Karp (plain Python)", network.local_edmonds_karp, "value"),
        "project": [("cognition.graph", "PR #140 op: shortest paths only; no flow")],
        "candidates": (
            PackageCandidate("networkx", "networkx", "networkx.max_flow",
                             ("networkx/__init__.py", "networkx/classes/", "networkx/algorithms/flow/",
                              "networkx/utils/", "networkx/exception.py"),
                             "preflow-push maximum flow (networkx.maximum_flow)",
                             "integer capacities, total at most 2^31-1; directed arcs"),
            PackageCandidate("scipy", "scipy.sparse.csgraph", "scipy.max_flow",
                             ("scipy/__init__.py", "scipy/sparse/csgraph/"),
                             "compiled Dinic maximum flow (scipy.sparse.csgraph.maximum_flow)",
                             "int32 capacities, total at most 2^31-1; directed arcs", ("numpy",))),
    },
}


CATALOG["lp.optimize"] = {
    "kind": "package", "description": "Maximize or minimize a linear objective under linear constraints and bounds, "
                                      "with a duality certificate",
    "oracle": linear.oracle_lp, "oracle_kind": "vertex enumeration in exact fractions (GREG)",
    "output_field": "certified", "normalize": linear.normalize_lp, "certify": linear.certify_lp,
    "certificate_error": linear.CertificateError, "runners": linear.RUNNERS, "follow_up": linear.follow_up_lp,
    "judge": linear.judge_lp, "probe": linear.probe_lp, "size": linear.size,
    "inputs": {"variables": "list", "objective": "dict", "constraints": "list"},
    "baseline": ("none simple at this size: GREG's exact vertex enumeration is exponential and serves only as "
                 "the oracle", None, None),
    "project": [("cognition.optimization", "PR #140 op: integer CP-SAT models; no continuous optimum and no dual "
                                           "certificate"),
                ("cognition.cortex.optimization.cpsat", "cortex organ: integer variables only")],
    "candidates": (
        PackageCandidate("scipy", "scipy.optimize", "scipy.lp", ("scipy/__init__.py", "scipy/optimize/_linprog",
                                                                  "scipy/optimize/_highspy/", "scipy/optimize/__init__.py"),
                         "HiGHS dual simplex and interior point (scipy.optimize.linprog, method='highs')",
                         "at most 500 variables and 2,000 constraints; coefficients up to 1e9", ("numpy",)),
        PackageCandidate("ortools", "ortools.linear_solver.pywraplp", "ortools.lp",
                         ("ortools/__init__.py", "ortools/linear_solver/"),
                         "GLOP primal and dual simplex (ortools.linear_solver)",
                         "at most 500 variables and 2,000 constraints; coefficients up to 1e9",
                         ("numpy", "protobuf"))),
}
# Cognition mechanisms (directive 2026-10-07 section 24): installed engines Genesis forms for a residual geometry
# the Competency Compiler reports. ``signature`` is the geometry each serves; nothing else routes to it.
CATALOG[assignment.FUNCTION] = {
    "kind": "package", "signature": assignment.SIGNATURE, "evidence_type": "optimality_certificate",
    "description": "Least-cost (or greatest-value) assignment of the rows of a cost matrix to distinct columns, with "
                   "a linear-programming dual certificate",
    "oracle": assignment.oracle_assignment,
    "oracle_kind": "brute force over every injective map in exact integers, on fixed cases and on flock admission "
                   "instances from development seeds only (GREG)",
    "output_field": "certified", "normalize": assignment.normalize_assignment,
    "certify": assignment.certify_assignment, "certificate_error": assignment.CertificateError,
    "runners": assignment.RUNNERS, "judge": assignment.judge_assignment, "probe": assignment.probe_assignment,
    "size": assignment.size, "inputs": {"costs": "list", "maximize": "bool"},
    "baseline": ("local Hungarian algorithm (plain Python)", assignment.local_hungarian, "total"),
    "project": [("cognition.optimization", "integer CP-SAT models: an assignment must first be written as a formal "
                                           "model, and no dual certificate is returned")],
    "same_engine": [("networkx", "bipartite.minimum_weight_full_matching defers to SciPy's linear_sum_assignment: "
                                 "the same engine, not an alternative")],
    "candidates": (
        PackageCandidate("scipy", "scipy.optimize", "scipy.assignment",
                         ("scipy/__init__.py", "scipy/optimize/__init__.py", "scipy/optimize/_lsap"),
                         "shortest augmenting path assignment in compiled code (scipy.optimize.linear_sum_assignment)",
                         "rectangular matrices up to 200 x 200; finite costs up to 1e12 in magnitude, solved in "
                         "float64; GREG's certificate is exact", ("numpy",)),
        PackageCandidate("ortools", "ortools.graph.python.linear_sum_assignment", "ortools.assignment",
                         ("ortools/__init__.py", "ortools/graph/python/__init__.py",
                          "ortools/graph/python/linear_sum_assignment"),
                         "cost-scaling assignment (OR-Tools SimpleLinearSumAssignment)",
                         "integer costs only: GREG's runner refuses non-integer costs, so it cannot qualify where the "
                         "frozen oracle has real-valued costs; rectangular matrices padded with zero-cost rows")),
}
for _spec in CATALOG.values():
    if _spec.get("kind") == "package":
        _spec.setdefault("certificate_error", network.CertificateError)
        _spec.setdefault("runners", network.RUNNERS)

COGNITION_SEARCH = ["attached", "verified_detached", "genome_library", "installed_package", "builder", "founder"]
CONTROL_INPUTS = ("formalization_complete",)        # compiler-level flags carried in data; no method reads them


def is_cognition_deficit(function: str) -> bool:
    """A residual geometry the Competency Compiler reported (``cognition.<class>:<sub>``), as opposed to a
    capability's own function (``cognition.exact``) or a catalogued mechanism function."""
    return function.startswith("cognition.") and ":" in function and function not in CATALOG


def cognition_record(function: str, deficit: dict | None = None) -> dict:
    """The residual geometry Genesis searches for: the epistemic class and the inputs the request carries.

    Built from the compiler's ``capability_deficit`` when the mission engine passes it; otherwise from the
    function name alone, with no inputs (nothing then matches by inputs, so the search ends with the founder)."""
    from greg.cognition.genomes.contract import EPISTEMIC_CLASSES
    head, _, sub = function.removeprefix("cognition.").partition(":")
    raw = deficit if isinstance(deficit, dict) else {}
    geometry = raw.get("geometry") if isinstance(raw.get("geometry"), dict) else {}
    declared = geometry.get("geometry", head)
    inputs = raw.get("required_inputs") if isinstance(raw.get("required_inputs"), list) else []
    named = raw.get("acquisition_candidates") if isinstance(raw.get("acquisition_candidates"), list) else []
    return {"geometry": declared if declared in EPISTEMIC_CLASSES else None,
            "subgeometry": str(geometry.get("subgeometry") or sub or "")[:120] or None,
            "required_inputs": sorted({x for x in inputs if isinstance(x, str) and 0 < len(x) <= 64})[:64],
            "inputs_known": isinstance(raw.get("required_inputs"), list),
            "named_by_compiler": [{"mechanism": str(c.get("mechanism"))[:200],
                                   "supersedes": str(c.get("supersedes") or c.get("subregion") or "")[:120]}
                                  for c in named[:5] if isinstance(c, dict)]}


def cognition_mechanisms(inputs, geometry: str | None) -> list[str]:
    """Catalogued installed mechanisms whose declared geometry serves this residual: the same epistemic class (or
    none declared), every required input present, and no input the mechanism would not read."""
    provided = set(inputs) - set(CONTROL_INPUTS)
    out = []
    for function, spec in CATALOG.items():
        signature = spec.get("signature")
        if not signature or (geometry and geometry not in signature["classes"]):
            continue
        if set(signature["required"]) <= provided <= set(signature["required"]) | set(signature["optional"]):
            out.append(function)
    return out


def formed_cognition(registry, data: dict, geometry: str | None) -> list:
    """(manifest, adapter) for every usable capability Genesis formed for this geometry. Usable means ATTACHED,
    which only the founder's command does for these."""
    out = []
    for function in cognition_mechanisms(data, geometry):
        for manifest in registry.by_function(function):
            if is_formed(manifest) and registry.usable(manifest.capability_id)[0]:
                out.append((manifest, registry.adapters[manifest.capability_id]))
    return out


def run_formed(manifest, adapter, data: dict) -> dict:
    """One call of a formed cognition mechanism on the inputs its signature reads; the adapter re-pins the package
    and accepts the engine's claim only on GREG's certificate (CapabilityError otherwise)."""
    signature = CATALOG[manifest.function]["signature"]
    params = {k: data[k] for k in (*signature["required"], *signature["optional"]) if k in data}
    with tempfile.TemporaryDirectory(prefix="greg-formed-") as tmp:
        return adapter(params, InvocationContext(workspace=Path(tmp), read_roots=(), secrets=None, manifest=manifest))


def package_adapter(function: str, candidate: PackageCandidate):
    """Adapter bound to one qualified package; re-pinned and certificate-checked on every call."""
    spec = CATALOG[function]

    def adapter(params, ctx: InvocationContext):
        request = spec["normalize"](params)          # competence is enforced before the engine sees anything
        prov = ctx.manifest.provenance
        dist = mechanisms.installed(candidate.distribution)
        if dist is None or dist.version != prov["version"] \
                or mechanisms.digest(dist, candidate.digest_paths)[0] != prov["package_digest"]:
            raise CapabilityError("capability refused: package changed since qualification; quarantine required")
        [claim] = mechanisms.run(candidate, spec["runners"][candidate.runner], [request],
                                 location=prov["location"], version=prov["version"])
        if "error" in claim:
            raise CapabilityError(f"capability refused: package {candidate.distribution} raised "
                                  f"{claim['error'][:200]}")
        try:
            answer = spec["certify"](request, claim["result"])
            if answer.get("follow_up") and spec.get("follow_up"):
                # The engine's negative claim is proved or refuted by a second, certified solve.
                extras = mechanisms.run(candidate, spec["runners"][candidate.runner], answer["follow_up"],
                                        location=prov["location"], version=prov["version"])
                if any("error" in e for e in extras):
                    raise CapabilityError(f"capability refused: package {candidate.distribution} raised "
                                          f"{next(e['error'] for e in extras if 'error' in e)[:200]}")
                answer = spec["follow_up"](request, answer, [e["result"] for e in extras])
        except spec["certificate_error"] as exc:
            raise CapabilityError(f"capability refused: package output failed its certificate: {exc}") from exc
        answer.pop("follow_up", None)
        return {**answer, "engine": f"{candidate.distribution} {prov['version']}", "license": prov["license"],
                "authority_created": False}
    return adapter


def catalog_adapter(function: str, candidate: Candidate, binary: str):
    """Adapter bound to one verified binary; re-checked against its content hash."""
    spec = CATALOG[function]

    def adapter(params, ctx: InvocationContext):
        path = Path(params["path"]).resolve()
        roots = ctx.read_roots + (ctx.workspace,)
        if not any(path == Path(r).resolve() or Path(r).resolve() in path.parents for r in roots):
            raise CapabilityError(f"path {path} outside permitted roots")
        expected = ctx.manifest.provenance.get("binary_sha256")
        if expected and hashlib.sha256(Path(binary).read_bytes()).hexdigest() != expected:
            raise CapabilityError("installed binary changed since verification; quarantine required")
        ctx.workspace.mkdir(parents=True, exist_ok=True)
        argv = [binary if t == "{binary}" else str(path) if t == "{file}" else t for t in candidate.argv]
        proc = run_isolated(argv, cwd=ctx.workspace)
        if proc.returncode:
            raise CapabilityError(f"{candidate.binary_name} exited {proc.returncode}")
        value = PARSERS[candidate.parse](proc.stdout.decode("utf-8", errors="replace"))
        return {spec["output_field"]: value, "path": str(path)}
    return adapter


def qualify_package(function: str, candidate: PackageCandidate, card: dict, seed: int) -> tuple[bool, dict]:
    """Frozen oracle plus a scale probe, in one isolated run; compared with the simplest local implementation."""
    spec = CATALOG[function]
    cases = spec["oracle"](seed)
    probe = spec["normalize"](spec["probe"](seed))
    requests = [spec["normalize"](c["input"]) for c in cases] + [probe]
    report = {"cases": len(cases), "failures": [], "isolation": "no-network interpreter", "platform": sys.platform,
              "oracle": spec["oracle_kind"], "certificate": "GREG-owned, exact; shares no code with the package"}
    started = time.perf_counter()
    try:
        claims = mechanisms.run(candidate, spec["runners"][candidate.runner], requests, location=card["location"],
                                version=card["version"], cpu_seconds=60)
    except CapabilityError as exc:
        report["failures"].append({"case": "all", "error": str(exc)[:300]})
        return False, report
    wall = time.perf_counter() - started
    named = cases + [{"name": "scale-probe"}]
    answers = []
    for case, request, claim in zip(named, requests, claims):
        if "error" in claim:
            report["failures"].append({"case": case["name"], "error": claim["error"][:160]})
            answers.append(None)
            continue
        try:
            answers.append(spec["certify"](request, claim["result"]))
        except spec["certificate_error"] as exc:
            report["failures"].append({"case": case["name"], "certificate": str(exc)[:160]})
            answers.append(None)
    pending = [i for i, a in enumerate(answers) if a and a.get("follow_up") and spec.get("follow_up")]
    if pending:                                   # negative claims are proved by a second, certified solve
        flat = [r for i in pending for r in answers[i]["follow_up"]]
        try:
            extras = mechanisms.run(candidate, spec["runners"][candidate.runner], flat, location=card["location"],
                                    version=card["version"], cpu_seconds=60)
        except CapabilityError as exc:
            extras = [{"error": str(exc)}] * len(flat)
        position = 0
        for i in pending:
            group = extras[position:position + len(answers[i]["follow_up"])]
            position += len(answers[i]["follow_up"])
            try:
                if any("error" in e for e in group):
                    raise spec["certificate_error"](next(e["error"] for e in group if "error" in e)[:160])
                answers[i] = spec["follow_up"](requests[i], answers[i], [e["result"] for e in group])
            except spec["certificate_error"] as exc:
                report["failures"].append({"case": named[i]["name"], "certificate": str(exc)[:160]})
                answers[i] = None
    for case, answer in zip(named, answers):
        if answer is not None and "expected" in case and not spec["judge"](answer, case["expected"]):
            report["failures"].append({"case": case["name"], "expected": str(case["expected"])[:120],
                                       "got": str({k: answer.get(k) for k in case["expected"]})[:120]})
    probe_answer = answers[-1]
    report["scale_probe"] = {**spec["size"](probe), "package_solve_seconds": round(claims[-1].get("seconds", 0.0), 4),
                             "package_run_seconds_with_interpreter": round(wall, 3),
                             "certified": bool(probe_answer and probe_answer.get("certified"))}
    name, local, field = spec["baseline"]
    if local is None:
        report["scale_probe"]["simplest_local_alternative"] = name
    else:
        local_started = time.perf_counter()
        local_answer = local(probe)
        report["scale_probe"].update({"simplest_local_alternative": name,
                                      "local_seconds": round(time.perf_counter() - local_started, 4),
                                      "agrees_with_local": probe_answer is not None
                                      and probe_answer[field] == local_answer[field]})
    return not report["failures"] and report["scale_probe"]["certified"], report


FORMED = ("built:", "installed:")      # providers Genesis formed, and therefore can re-form
FAULT_MARKERS = ("capability refused: built capability", "capability refused: installed binary changed",
                 "capability refused: package")


def is_formed(manifest) -> bool:
    return manifest.provider.startswith(FORMED)


def is_capability_fault(manifest, reason: str) -> bool:
    """A failure of the capability itself, not of the world it reads (missing file, scope)."""
    if not is_formed(manifest):
        return False
    binary = Path(manifest.binaries[0]).name if manifest.binaries else None
    return any(m in reason for m in FAULT_MARKERS) or bool(binary and f"capability refused: {binary} exited" in reason)


class Genesis:
    """The resourceful capability-formation loop, recorded on the canonical spine."""

    def __init__(self, *, journal: Journal, registry, workspace_root: Path, builder=None, read_roots=()):
        self.journal, self.registry = journal, registry
        self.workspace_root, self.builder = Path(workspace_root), builder
        self.read_roots = tuple(Path(r).resolve() for r in read_roots)
        self.builder_cap = getattr(builder, "max_budget_usd", None)   # the builder's own ceiling, never ratcheted
        self.store = self.workspace_root.parent / "capabilities" / "built"   # content-addressed built sources
        self.objects = ArtifactStore(self.store, legacy_source_suffix=".py")  # preserve existing bodies' paths

    # -- queries used by the mission engine --------------------------------------
    def find_attached(self, function: str):
        for manifest in self.registry.by_function(function):
            ok, _ = self.registry.usable(manifest.capability_id)
            if ok:
                return manifest
        return None

    # -- restart: rebuild acquired adapters from retained provenance -------------
    def restore(self):
        states = {}
        for event in self.journal.replay("capability."):
            data = event.payload
            if event.type == "greg.capability.registered" and data["manifest"]["provider"].startswith(FORMED):
                # a re-verified (repaired) capability starts again from its registration state
                states[data["manifest"]["capability_id"]] = (data, data.get("state", "VERIFIED"))
            elif event.type == "greg.capability.state" and data["capability_id"] in states:
                states[data["capability_id"]] = (states[data["capability_id"]][0], data["state"])
        for cid, (data, state) in states.items():
            manifest = CapabilityManifest.from_dict(data["manifest"])
            origin = data["origin"]
            if origin.get("kind") == "built":
                address = "sha256:" + origin["source_sha256"]
                path = self.objects.path(address)
                try:
                    self.objects.read(address)
                    intact = True
                except CapabilityError:
                    intact = False
                self.registry.register(manifest, builders.built_adapter(origin["contract"], path, origin["source_sha256"]),
                                       state=state if intact else "QUARANTINED")
                if not intact and state != "QUARANTINED":
                    self.journal.record("capability.state", {"capability_id": cid, "state": "QUARANTINED",
                                                             "why": "built source missing or changed since verification"},
                                        key=[cid, "quarantine", origin["source_sha256"]])
                continue
            if origin.get("kind") == "package":
                self._restore_package(cid, manifest, origin, state)
                continue
            binary = manifest.binaries[0]
            candidate = Candidate(origin["binary_name"], tuple(origin["argv"]), origin["parse"])
            intact = Path(binary).exists() and hashlib.sha256(
                Path(binary).read_bytes()).hexdigest() == manifest.provenance.get("binary_sha256")
            self.registry.register(manifest, catalog_adapter(origin["function"], candidate, binary),
                                   state=state if intact else "QUARANTINED")
            if not intact and state != "QUARANTINED":
                self.journal.record("capability.state", {"capability_id": cid, "state": "QUARANTINED",
                                                         "why": "binary missing or changed since verification"},
                                    key=[cid, "quarantine", manifest.provenance.get("binary_sha256")])

    def _restore_package(self, cid, manifest, origin, state):
        """A qualified package is trusted again only if its pinned files and shared dependencies are unchanged."""
        candidate = next((c for c in CATALOG.get(origin["function"], {}).get("candidates", ())
                          if isinstance(c, PackageCandidate) and c.runner == origin["runner"]), None)
        why = None
        dist = mechanisms.installed(origin["distribution"])
        if candidate is None:
            why = "no package candidate with this runner in the catalog"
        elif dist is None or dist.version != manifest.provenance.get("version"):
            why = "package missing or a different version since qualification"
        else:
            try:
                if mechanisms.digest(dist, candidate.digest_paths)[0] != manifest.provenance.get("package_digest"):
                    why = "pinned package files changed since qualification"
                elif mechanisms.shared(candidate.common_mode) != manifest.provenance.get("common_mode"):
                    why = "a shared dependency changed since qualification"
            except CapabilityError as exc:
                why = str(exc)
        adapter = package_adapter(origin["function"], candidate) if candidate else (lambda params, ctx: None)
        self.registry.register(manifest, adapter, state="QUARANTINED" if why else state)
        if why and state != "QUARANTINED":
            self.journal.record("capability.state", {"capability_id": cid, "state": "QUARANTINED", "why": why},
                                key=[cid, "quarantine", manifest.provenance.get("package_digest"), why])

    # -- the loop -------------------------------------------------------------------
    def _deficit_for(self, mission_id: str, function: str):
        """The open deficit for (mission, function), else the id of the next generation.

        Reusing an open deficit keeps a restart mid-search idempotent; a new generation
        after a resolved one lets the same function be lost and re-formed repeatedly."""
        opened = [e.payload for e in self.journal.replay("deficit.opened")
                  if e.payload["mission_id"] == mission_id and e.payload["function"] == function]
        resolved = {e.payload["deficit_id"] for e in self.journal.replay("deficit.resolved")}
        if opened and opened[-1]["deficit_id"] not in resolved:
            return opened[-1]["deficit_id"], opened[-1]
        seed = {"mission": mission_id, "function": function}
        if opened:
            seed["generation"] = len(opened)
        return "deficit-" + sha256_json(seed)[7:31], None

    def repair(self, *, mission, capability_id: str, failure: str, params: dict, now):
        """A formed capability failed in service: quarantine it with the evidence and re-form the function."""
        manifest = self.registry.manifests[capability_id]
        if not is_formed(manifest):
            return None
        incident = sha256_json({"capability_id": capability_id, "failure": failure})
        self.registry.set_state(capability_id, "QUARANTINED")
        self.journal.record("capability.state", {"capability_id": capability_id, "state": "QUARANTINED",
                                                 "why": "failed in service: " + failure[:300],
                                                 "by": "self-repair (repeated capability fault)",
                                                 "mission_id": mission.mission_id},
                            key=[capability_id, "quarantine", incident])
        return self.resolve(mission=mission, function=manifest.function, now=now,
                            purpose=f"self-repair of {capability_id}",
                            repair={"capability_id": capability_id, "failure": failure[:300],
                                    "replay_path": params.get("path")})

    def attach_candidates(self, mission_id: str, function: str) -> list[str]:
        """Capabilities the latest deficit for a cognition (mission, function) found registered and still withheld
        (VERIFIED). They carry other function names than the deficit, so the mission's blocker and founder ask name
        them. One already attached is no longer a decision to ask for (and must not unblock a deficit it caused)."""
        if not is_cognition_deficit(function):
            return []
        opened = [e.payload["deficit_id"] for e in self.journal.replay("deficit.opened")
                  if e.payload["mission_id"] == mission_id and e.payload["function"] == function]
        if not opened:
            return []
        return list(dict.fromkeys(e.payload["capability_id"] for e in self.journal.replay("deficit.awaiting_attach")
                                  if e.payload["deficit_id"] == opened[-1]
                                  and self.registry.state.get(e.payload["capability_id"]) == "VERIFIED"))

    def resolve(self, *, mission, function: str, purpose: str, now, repair: dict | None = None,
                deficit: dict | None = None):
        found = self.find_attached(function)
        if found:
            return found
        if is_cognition_deficit(function):
            return self._resolve_cognition(mission, function, purpose, now, repair, deficit)
        deficit_id, existing = self._deficit_for(mission.mission_id, function)
        if existing is not None:
            repair = existing.get("repair") or repair
        if repair is None:  # a formed implementation was lost (quarantined at restart): this is a repair too
            lost = [m.capability_id for m in self.registry.by_function(function)
                    if is_formed(m) and self.registry.state[m.capability_id] == "QUARANTINED"]
            if lost:
                repair = {"capability_id": lost[-1], "failure": "quarantined: source or binary changed since "
                                                                "verification", "replay_path": None}
        spec = CATALOG.get(function)
        contract = next((c for c in mission.spec.get("capability_specs", []) if c["function"] == function), None)
        seed = int(sha256_json({"deficit": deficit_id})[7:15], 16)
        acceptance = {"oracle": function if spec else None, "seed": seed,
                      "vector_digest": sha256_json([{k: (v.hex() if isinstance(v, bytes) else v)
                                                     for k, v in c.items()} for c in spec["oracle"](seed)])
                      if spec else None}
        if spec is None and contract is not None:
            acceptance = {"oracle": "founder-signed mission contract", "public_examples": len(contract["examples"]),
                          "held_out_vectors": len(contract["held_out"]),
                          "vector_digest": sha256_json([contract["examples"], contract["held_out"]])}
        # A deficit is VERIFIED only by three facts (mechanism from PR #70 capabilities/deficit.py):
        # something requires the function, resolving it failed, and no registered implementation can serve.
        examined = [{"capability_id": m.capability_id, "state": self.registry.state[m.capability_id],
                     "why_not": self.registry.usable(m.capability_id)[1]} for m in self.registry.by_function(function)]
        verification = {"required_by": {"mission_id": mission.mission_id, "purpose": purpose},
                        "failed": f"no ATTACHED, usable implementation of {function!r} resolved",
                        "unserviceable": examined or "no registered implementation of this function",
                        "verified": True}
        if existing is None:
            opened = {"deficit_id": deficit_id, "mission_id": mission.mission_id, "function": function,
                      "purpose": purpose, "acceptance": acceptance, "at": iso(now), "verification": verification,
                      "search_order": ["attached", "verified_detached", "installed_software", "builder", "founder"]}
            if spec and spec.get("kind") == "package":
                opened["search_order"] = ["attached", "verified_detached", "existing_project", "installed_package",
                                          "builder", "founder"]
            if repair is not None:
                opened["repair"] = repair
            self.journal.record("deficit.opened", opened, key=deficit_id)

        # 2. registered but detached
        for manifest in self.registry.by_function(function):
            if self.registry.state[manifest.capability_id] == "VERIFIED":
                self._route(deficit_id, "verified_detached", "found", manifest.capability_id)
                return self._attach(mission, manifest, deficit_id, now)
        self._route(deficit_id, "verified_detached", "none", None)

        if spec is None:
            self._route(deficit_id, "installed_software", "no catalogued installed tool or oracle for this function",
                        None)
            return self._builder_route(mission, function, deficit_id, now, contract, repair)

        if spec.get("kind") == "package":
            found = self._package_route(mission, function, spec, deficit_id, seed, repair, now)
            if found is not False:
                return found
            return self._builder_route(mission, function, deficit_id, now, contract, repair)

        # 3. installed commodity software
        for candidate in spec["candidates"]:
            binary = installed_binary(candidate.binary_name)
            if binary is None:
                self._route(deficit_id, "installed_software", f"{candidate.binary_name} not installed", None)
                continue
            manifest = self._manifest_for(function, candidate, binary, deficit_id)
            # A signed founder detachment is a choice about this identity, not a
            # missing implementation that discovery may silently re-register.
            if self.registry.state.get(manifest.capability_id) == "DETACHED":
                self._route(deficit_id, "installed_software", "founder-detached; explicit attach required",
                            manifest.capability_id)
                continue
            passed, report = self._verify(function, candidate, binary, seed, manifest)
            self.journal.record("genesis.verified", {"deficit_id": deficit_id, "capability_id": manifest.capability_id,
                                                     "passed": passed, "report": report,
                                                     "verifier": "frozen oracle, independent of candidate"},
                                key=[deficit_id, manifest.capability_id])
            if not passed:
                self._route(deficit_id, "installed_software", f"{candidate.binary_name} failed verification", None)
                continue
            self.registry.register(manifest, catalog_adapter(function, candidate, binary), state="VERIFIED")
            self.journal.record("capability.registered", {
                "manifest": manifest.to_dict(), "state": "VERIFIED", "deficit_id": deficit_id,
                "origin": {"function": function, "binary_name": candidate.binary_name,
                           "argv": list(candidate.argv), "parse": candidate.parse}},
                key=[manifest.capability_id, manifest.digest()])
            self._route(deficit_id, "installed_software", "acquired", manifest.capability_id)
            return self._attach(mission, manifest, deficit_id, now)
        return self._builder_route(mission, function, deficit_id, now, contract, repair)

    def _resolve_cognition(self, mission, function, purpose, now, repair, deficit):
        """A residual geometry from the Competency Compiler: the registered repertoire, then installed open-source
        mechanisms, then a builder and the founder. Whatever is found waits for the founder's attach."""
        deficit_id, existing = self._deficit_for(mission.mission_id, function)
        record = (existing or {}).get("cognition") or cognition_record(function, deficit)
        if existing is not None:
            repair = existing.get("repair") or repair
        mechanisms = cognition_mechanisms(record["required_inputs"], record["geometry"])
        contract = next((c for c in mission.spec.get("capability_specs", []) if c["function"] == function), None)
        seed = int(sha256_json({"deficit": deficit_id})[7:15], 16)
        if existing is None:
            examined = [{"capability_id": m.capability_id, "state": self.registry.state[m.capability_id],
                         "why_not": self.registry.usable(m.capability_id)[1]} for m in self.registry.by_function(function)]
            failed = ((deficit or {}).get("verification") or {}).get("failed") if isinstance(deficit, dict) else None
            opened = {"deficit_id": deficit_id, "mission_id": mission.mission_id, "function": function,
                      "purpose": purpose, "at": iso(now), "search_order": COGNITION_SEARCH, "cognition": record,
                      "acceptance": {"oracle": {f: CATALOG[f]["oracle_kind"] for f in mechanisms} or None,
                                     "seed": seed,
                                     "vector_digest": sha256_json({f: CATALOG[f]["oracle"](seed) for f in mechanisms})
                                     if mechanisms else None},
                      "verification": {"required_by": {"mission_id": mission.mission_id, "purpose": purpose},
                                       "failed": str(failed or f"no ATTACHED, usable implementation of {function!r} "
                                                                "resolved")[:300],
                                       "unserviceable": examined or "no registered implementation of this function",
                                       "verified": True}}
            if repair is not None:
                opened["repair"] = repair
            self.journal.record("deficit.opened", opened, key=deficit_id)
        for named in record["named_by_compiler"]:
            self._route(deficit_id, "frozen_evidence", f"the compiler names {named['mechanism']} (in place of "
                                                       f"{named['supersedes']}) from frozen held-out evidence", None)
        # 2. registered for this exact function and withheld: the founder attaches it
        for manifest in self.registry.by_function(function):
            if self.registry.state[manifest.capability_id] == "VERIFIED":
                self._route(deficit_id, "verified_detached", "found", manifest.capability_id)
                return self._attach(mission, manifest, deficit_id, now)
        self._route(deficit_id, "verified_detached", "none", None)
        # 3. the registered repertoire: the simplest route is a family GREG already has
        if self._genome_library(deficit_id, record):
            self._route(deficit_id, "installed_package", "not searched: a registered intelligence fits this geometry; "
                                                         "attaching it is the simpler route", None)
            self._route(deficit_id, "founder", "escalated", None)
            return None
        # 4. installed open-source mechanisms that declare this geometry (DEPEND)
        if not record["inputs_known"]:
            self._route(deficit_id, "installed_package", "the deficit names no inputs, so no mechanism can be matched "
                                                         "to it", None)
        elif not mechanisms:
            self._route(deficit_id, "installed_package", "no catalogued open-source mechanism serves this geometry "
                                                         f"with inputs {record['required_inputs'][:12]}", None)
        for mechanism in mechanisms:              # formed for an earlier deficit and still awaiting the founder
            for manifest in self.registry.by_function(mechanism):
                if is_formed(manifest) and self.registry.state[manifest.capability_id] == "VERIFIED":
                    self._route(deficit_id, "installed_package", "qualified earlier; awaiting the founder's attach",
                                manifest.capability_id)
                    return self._attach(mission, manifest, deficit_id, now)
        for mechanism in mechanisms:
            found = self._package_route(mission, mechanism, CATALOG[mechanism], deficit_id, seed, repair, now)
            if found is not False:
                return found
        return self._builder_route(mission, function, deficit_id, now, contract, repair)

    def _genome_library(self, deficit_id: str, record: dict) -> list[str]:
        """Registered intelligences whose native geometry and inputs fit the residual; returns attach candidates.

        The fit rule is the Competency Compiler's (native epistemic class; every native input present), and so is
        its frozen negative evidence: an excluded admission status or a composition-only stage is never a
        candidate. A registered, withheld (VERIFIED) family is reported for the founder to attach; GREG never
        attaches it. Detached, quarantined or unregistered families are reported, not offered."""
        from greg.cognition import catalog, compiler
        from greg.cognition.genomes import library
        provided, declared = set(record["required_inputs"]), record["geometry"]
        evidence, genomes = compiler.evidence_index(), library.executables()
        found, near, noted = [], [], False
        for family, (_, operations, classes, _, _) in sorted(catalog.FAMILIES.items()):
            if declared and declared not in classes:
                continue
            cid = "cognition." + family
            if family in genomes:
                genome = genomes[family].genome
                needs, standalone = [tuple(genome.required_inputs)], genome.standalone_decision
                measured = evidence.get("genomes", {}).get(family, {})
                status = measured.get("status", "UNEVALUATED")
                if measured.get("version") and measured["version"] != genome.version \
                        and status not in compiler.NOT_POSITIVE:
                    status = "UNEVALUATED"         # positive evidence binds the version measured
            else:
                needs = [compiler.NATIVE_INPUTS[op] for op in operations if op in compiler.NATIVE_INPUTS]
                standalone, status = True, "UNEVALUATED"
            fit = next((need for need in needs if set(need) <= provided), None)
            if fit is None:
                close = next((need for need in needs if set(need) & provided), None)
                if declared and close:
                    near.append((cid, sorted(set(close) - provided)))
                continue
            state = self.registry.state.get(cid)
            why = ("composition stage only (no standalone decision)" if not standalone
                   else f"frozen admission status {status}" if status in compiler.EXCLUDED
                   else "not registered on this body" if state is None
                   else "founder-detached; explicit attach required" if state == "DETACHED"
                   else f"attached ({self.registry.usable(cid)[1]})" if state == "ATTACHED"
                   else f"state {state}" if state != "VERIFIED" else None)
            if why:
                self._route(deficit_id, "genome_library", f"{cid} fits but is not a candidate: {why}", cid)
                noted = True
                continue
            found.append(cid)
            self._route(deficit_id, "genome_library", f"attach candidate: {cid} ({status}) fits by native class and "
                                                      f"inputs {sorted(fit)}; registered and withheld; GREG does "
                                                      "not attach it", cid)
            self.journal.record("deficit.awaiting_attach", {
                "deficit_id": deficit_id, "capability_id": cid, "admission_status": status,
                "why": "a registered, withheld intelligence fits the residual geometry; attaching it is the "
                       "founder's decision"}, key=[deficit_id, "await", cid, status])
        for cid, missing in near[:5]:
            self._route(deficit_id, "genome_library", f"{cid} has this geometry but also needs inputs {missing}", cid)
        if not found and not noted and not near:
            self._route(deficit_id, "genome_library", "no registered intelligence has this geometry and these inputs",
                        None)
        return found

    def _package_route(self, mission, function, spec, deficit_id, seed, repair, now):
        """Existing project mechanisms first, then installed open-source packages (DEPEND).

        Returns the attached manifest, None when one awaits the founder's attach, or False
        when no package qualified (the caller continues to the builder route)."""
        for cid, why_not in spec.get("project", ()):
            self._route(deficit_id, "existing_project", f"{cid}: {why_not}", cid)
        for name, why in spec.get("same_engine", ()):
            self._route(deficit_id, "installed_package", f"{name}: {why}", None)
        for candidate in spec["candidates"]:
            dist = mechanisms.installed(candidate.distribution)
            if dist is None:
                self._route(deficit_id, "installed_package", f"{candidate.distribution} not installed (GREG installs "
                                                             "nothing; you may)", None)
                continue
            try:
                card = mechanisms.card(candidate, function, dist)
            except CapabilityError as exc:
                self._route(deficit_id, "installed_package", f"{candidate.distribution} cannot be pinned: {exc}"[:300],
                            None)
                continue
            manifest = self._package_manifest(function, candidate, card, deficit_id)
            if self.registry.state.get(manifest.capability_id) == "DETACHED":
                self._route(deficit_id, "installed_package", "founder-detached; explicit attach required",
                            manifest.capability_id)
                continue
            if "signature" in spec and self.registry.state.get(manifest.capability_id) == "ATTACHED":
                # a cognition deficit despite this attached mechanism: the compiler's receipt says why; a
                # re-qualification here would silently withdraw the founder's attach
                self._route(deficit_id, "installed_package", "attached, yet the compiler obtained no certified answer "
                                                             "from it (its receipt records why)",
                            manifest.capability_id)
                continue
            if repair and repair.get("capability_id") == manifest.capability_id:
                self._route(deficit_id, "installed_package", "this package failed in service; a different provider is "
                                                             "preferred (the founder may re-attach it)",
                            manifest.capability_id)
                continue
            passed, report = qualify_package(function, candidate, card, seed)
            self.journal.record("genesis.verified", {"deficit_id": deficit_id, "capability_id": manifest.capability_id,
                                                     "passed": passed, "report": report, "mechanism": card,
                                                     "verifier": "frozen oracle and GREG certificate, independent of "
                                                                 "the package"},
                                key=[deficit_id, manifest.capability_id, card["package_digest"]])
            if not passed:
                self._route(deficit_id, "installed_package", f"{candidate.distribution} failed qualification", None)
                continue
            manifest = self._package_manifest(function, candidate, card, deficit_id, report)
            self.registry.register(manifest, package_adapter(function, candidate), state="VERIFIED")
            self.journal.record("capability.registered", {
                "manifest": manifest.to_dict(), "state": "VERIFIED", "deficit_id": deficit_id,
                "origin": {"kind": "package", "function": function, "distribution": candidate.distribution,
                           "module": candidate.module, "runner": candidate.runner}},
                key=[manifest.capability_id, manifest.digest()])
            self._route(deficit_id, "installed_package", "acquired", manifest.capability_id)
            return self._attach(mission, manifest, deficit_id, now)
        return False

    def _package_manifest(self, function, candidate: PackageCandidate, card: dict, deficit_id: str,
                          report: dict | None = None) -> CapabilityManifest:
        spec = CATALOG[function]
        runner = spec["runners"][candidate.runner]
        return CapabilityManifest(
            capability_id=f"acquired.{function}.{candidate.distribution}", version="1.0.0",
            provider=f"installed:python:{candidate.distribution}=={card['version']}", function=function,
            description=spec["description"], route="internal", consequence_class="read_only",
            inputs=spec.get("inputs", {"edges": "list", "source": "str"}),
            outputs={spec["output_field"]: "bool", "certificate": "dict"},
            target_prefix="cognition:", filesystem="none", retry_safe=True,
            tests=(f"frozen-oracle:{function}", "certificate:every-call"), strengthens=("capability_formation", "proof"),
            provenance={**card, "deficit_id": deficit_id, "runner": candidate.runner,
                        "runner_sha256": hashlib.sha256(runner.encode()).hexdigest(),
                        "builder": "none: installed open-source package acquired by search",
                        **({"qualification": report} if report else {})})

    def _route(self, deficit_id, route, result, capability_id):
        self.journal.record("genesis.route", {"deficit_id": deficit_id, "route": route, "result": result,
                                              "capability_id": capability_id},
                            key=[deficit_id, route, result, capability_id])

    def _replay_text(self, repair: dict | None):
        """The live input that broke the predecessor, read locally from the body's read roots."""
        path = (repair or {}).get("replay_path")
        if not path:
            return None
        path = Path(path).resolve()
        if not any(path == r or r in path.parents for r in self.read_roots) or not path.is_file():
            return None
        data = path.read_bytes()
        return data.decode("utf-8", errors="replace") if len(data) <= builders.MAX_INPUT else None

    def _builder_route(self, mission, function, deficit_id, now, contract=None, repair=None):
        """Commission the residual capability against the founder-frozen contract, verify, register."""
        if self.builder is None or contract is None:
            why = ("no builder attached (coding agent/human/model not connected)" if self.builder is None
                   else "the mission declares no contract for this function; nothing to build against")
            self._route(deficit_id, "builder", why, None)
            self._route(deficit_id, "founder", "escalated", None)
            return None
        # The signed build budget covers the function for the whole mission, across every repair
        # generation: a capability that keeps breaking cannot spend past what the founder signed.
        generations = {e.payload["deficit_id"] for e in self.journal.replay("deficit.opened")
                       if e.payload["mission_id"] == mission.mission_id and e.payload["function"] == function}
        spent = sum(e.payload.get("cost_usd") or 0.0 for e in self.journal.replay("genesis.built")
                    if e.payload["deficit_id"] in generations | {deficit_id})
        if contract["build_budget_usd"] <= 0 or spent >= contract["build_budget_usd"]:
            self._route(deficit_id, "builder", "no founder-signed build budget remains", None)
            self._route(deficit_id, "founder", "escalated", None)
            return None
        request = {"function": function, "description": contract["description"],
                   "returns": contract.get("returns", "a JSON value"), "examples": contract["examples"]}
        # Repair: the builder learns that and how the predecessor failed, never the live input itself.
        feedback = ([f"a previously verified implementation failed in service ({repair['failure'][:160]}); "
                     "it must handle arbitrary real input without raising"] if repair else None)
        replay = self._replay_text(repair)
        self.store.mkdir(parents=True, exist_ok=True)
        for attempt in (1, 2):
            remaining = contract["build_budget_usd"] - spent
            if remaining <= 0:   # re-checked per attempt: every attempt is spend
                self._route(deficit_id, "builder", "no founder-signed build budget remains", None)
                break
            if self.builder_cap is not None:   # per attempt: this function's remaining signed budget
                self.builder.max_budget_usd = min(self.builder_cap, remaining)
            try:
                built = self.builder.build(request, feedback)
            except Exception as exc:  # the builder is untrusted; its failure is evidence
                self._route(deficit_id, "builder", f"attempt {attempt} failed: {type(exc).__name__}: {exc}"[:300], None)
                break
            spent += float(built.get("cost_usd") or 0.0)
            source = built["source"]
            digest = hashlib.sha256(source.encode()).hexdigest()
            self.journal.record("genesis.built", {
                "deficit_id": deficit_id, "attempt": attempt, "builder": built["builder"],
                "prompt_sha256": built.get("prompt_sha256"), "source_sha256": digest,
                "cost_usd": built.get("cost_usd"), "sees": "description, signature, public examples only",
                "served_model": built.get("served_model"), "routes_tried": built.get("routes_tried"),
                **({"model_digest": built["model_digest"]} if built.get("model_digest") else {})},
                key=[deficit_id, attempt, digest])
            problems = builders.screen(source)
            path = self.objects.path("sha256:" + digest)
            if not problems:
                try:
                    self.objects.put(source.encode())
                except CapabilityError:
                    # Preserve the corrupt previous bytes as negative evidence,
                    # then restore only this candidate's independently screened bytes.
                    info = path.lstat()
                    if stat.S_ISLNK(info.st_mode):
                        actual = hashlib.sha256(os.readlink(path).encode()).hexdigest()
                    elif stat.S_ISREG(info.st_mode):
                        actual = hashlib.sha256(path.read_bytes()).hexdigest()
                    else:
                        raise CapabilityError("built-source path is not a regular file or symlink")
                    path.rename(path.with_name(f"{path.name}.unverified-{actual[:16]}"))
                    self.objects.put(source.encode())
            public_ok, public = (False, {}) if problems else builders.verify(path, contract["examples"])
            passed, report = (False, {"screen": problems}) if problems else builders.verify(
                path, contract["examples"] + contract["held_out"])
            report = {"screen": problems, "public": public, "cases": report.get("cases"),
                      "failed_cases": len(report.get("failures", [])), "isolation": report.get("isolation")}
            if passed and replay is not None:  # must not repeat the predecessor's failure on the live input
                try:
                    replayed = builders.execute(path, [replay])[0]
                except CapabilityError as exc:
                    replayed = {"ok": False, "error": str(exc)[:200]}
                report["service_replay"] = {"passed": bool(replayed.get("ok")),
                                            "error": None if replayed.get("ok") else str(replayed.get("error"))[:200]}
                passed = passed and bool(replayed.get("ok"))
            elif repair:
                report["service_replay"] = {"passed": None, "error": "live input not replayable inside read roots"}
            self.journal.record("genesis.verified", {"deficit_id": deficit_id, "capability_id": f"built:{digest}",
                                                     "passed": passed, "report": report,
                                                     "verifier": "founder-frozen held-out oracle; separate no-network "
                                                                 "interpreter; candidate never saw held-out vectors"},
                                key=[deficit_id, digest])
            if passed:
                manifest = self._built_manifest(function, contract, built, digest, deficit_id, report)
                if self.registry.state.get(manifest.capability_id) == "DETACHED":
                    self._route(deficit_id, "builder", "founder-detached; explicit attach required",
                                manifest.capability_id)
                    feedback = ["this identical implementation was detached by the founder; produce a different "
                                "implementation or escalate for explicit reattachment"]
                    continue
                origin = {"kind": "built", "function": function, "source_sha256": digest,
                          "contract": {"output_field": contract["output_field"]}}
                self.registry.register(manifest, builders.built_adapter(origin["contract"], path, digest),
                                       state="VERIFIED")
                self.journal.record("capability.registered", {"manifest": manifest.to_dict(), "state": "VERIFIED",
                                                              "deficit_id": deficit_id, "origin": origin},
                                    key=[manifest.capability_id, manifest.digest()])
                self._route(deficit_id, "builder", "built and verified", manifest.capability_id)
                return self._attach(mission, manifest, deficit_id, now)
            if report.get("service_replay", {}).get("passed") is False and not problems and not public.get("failures"):
                feedback = [f"your candidate passes the examples but raised on real input "
                            f"({report['service_replay']['error']}); handle arbitrary text without raising"]
                self._route(deficit_id, "builder", f"attempt {attempt} failed the service replay", None)
                continue
            feedback = problems or [f"input {json.dumps(contract['examples'][f['case']]['input_text'])[:200]} expected "
                                    f"{json.dumps(contract['examples'][f['case']]['expected'])} but got "
                                    f"{f.get('got', f.get('error'))}" for f in public.get("failures", [])
                                    if isinstance(f.get("case"), int)] or ["fails hidden acceptance cases; "
                                                                          "re-read the description precisely"]
            self._route(deficit_id, "builder", f"attempt {attempt} failed verification", None)
        self._route(deficit_id, "founder", "escalated", None)
        return None

    def _built_manifest(self, function, contract, built, digest, deficit_id, report) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id=f"built.{function}.{digest[:12]}", version="1.0.0", provider=f"built:{built['builder']}",
            function=function, description=contract["description"][:300], route="internal",
            consequence_class="read_only", inputs={"path": "str"},
            outputs={contract["output_field"]: contract.get("returns", "value"), "path": "str"},
            target_prefix="fs:", filesystem="read-scoped", retry_safe=True, tests=(f"founder-oracle:{deficit_id}",),
            strengthens=("capability_formation", "proof"),
            provenance={"source_sha256": digest, "builder": built["builder"], "prompt_sha256": built.get("prompt_sha256"),
                        **({"model_digest": built["model_digest"]} if built.get("model_digest") else {}),
                        "deficit_id": deficit_id, "oracle": "founder-signed held-out vectors",
                        "verification": report, "cost_usd": built.get("cost_usd"),
                        "license": "generated for this body by the named builder",
                        "runtime": "isolated interpreter per call; never in the body process"})

    def _manifest_for(self, function, candidate: Candidate, binary: str, deficit_id: str) -> CapabilityManifest:
        version = run_isolated([binary, "--version"], cwd=Path(tempfile.gettempdir()), timeout=10)
        version_text = (version.stdout or version.stderr).decode("utf-8", errors="replace").splitlines()[:1]
        return CapabilityManifest(
            capability_id=f"acquired.{function}.{candidate.binary_name}", version="1.0.0",
            provider="installed:" + binary, function=function, description=CATALOG[function]["description"],
            route="cli", consequence_class="read_only", inputs={"path": "str"},
            outputs={CATALOG[function]["output_field"]: "value"}, target_prefix="fs:", filesystem="read-scoped",
            binaries=(binary,), retry_safe=True, tests=(f"frozen-oracle:{function}",),
            strengthens=("capability_formation", "proof"),
            provenance={"binary": binary, "binary_sha256": hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
                        "version": version_text[0] if version_text else "unknown", "deficit_id": deficit_id,
                        "license": "system package; license not inspected by GREG",
                        "builder": "none: existing installed software acquired by search"})

    def _verify(self, function, candidate: Candidate, binary: str, seed: int, manifest) -> tuple[bool, dict]:
        spec = CATALOG[function]
        vectors = spec["oracle"](seed)
        failures = []
        with tempfile.TemporaryDirectory(prefix="greg-genesis-") as tmp:
            tmp = Path(tmp)
            ctx = InvocationContext(workspace=tmp, read_roots=(tmp,), secrets=None, manifest=manifest)
            adapter = catalog_adapter(function, candidate, binary)
            for case in vectors:
                path = tmp / case["name"]
                path.write_bytes(case["data"])
                try:
                    got = adapter({"path": str(path)}, ctx)[spec["output_field"]]
                except Exception as exc:  # candidate failure is evidence, not a crash
                    failures.append({"case": case["name"], "error": type(exc).__name__})
                    continue
                if got != case["expected"]:
                    failures.append({"case": case["name"], "got": str(got)[:80], "expected": str(case["expected"])[:80]})
        return (not failures, {"cases": len(vectors), "failures": failures, "isolation": "no-network subprocess",
                               "platform": sys.platform})

    def _attach(self, mission, manifest: CapabilityManifest, deficit_id: str, now):
        # Founder-signed pre-authorization only: read-only, and inside the cone. A capability formed for cognition
        # (directive section 24) is attached only by the founder's own command, never under a mission scope.
        cognition = manifest.function.startswith("cognition.")
        allowed = (not cognition and mission.spec.get("auto_attach", {}).get("max_consequence_class") == "read_only"
                   and manifest.consequence_class == "read_only"
                   and mission.cone._capability_inside(manifest.capability_id))
        if not allowed:
            why = ("a capability formed for cognition is attached only by the founder's own command" if cognition
                   else "mission scope does not pre-authorize this attach")
            self.journal.record("deficit.awaiting_attach", {"deficit_id": deficit_id,
                                                            "capability_id": manifest.capability_id, "why": why},
                                key=[deficit_id, "await", manifest.capability_id])
            return None
        self.registry.set_state(manifest.capability_id, "ATTACHED")
        self.journal.record("capability.state", {"capability_id": manifest.capability_id, "state": "ATTACHED",
                                                 "by": "founder-signed mission auto_attach (read_only)",
                                                 "mission_id": mission.mission_id, "deficit_id": deficit_id},
                            key=[manifest.capability_id, "attached", mission.mission_id, deficit_id])
        self.journal.record("deficit.resolved", {"deficit_id": deficit_id, "capability_id": manifest.capability_id,
                                                 "mission_id": mission.mission_id, "resume": "original mission",
                                                 "at": iso(now)}, key=[deficit_id, "resolved"])
        return manifest
