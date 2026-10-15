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
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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
from greg import builders, mechanisms, recombine
from greg.cognition import linear, network
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
for _spec in CATALOG.values():
    if _spec.get("kind") == "package":
        _spec.setdefault("certificate_error", network.CertificateError)
        _spec.setdefault("runners", network.RUNNERS)


def package_adapter(function: str, candidate: PackageCandidate):
    """Adapter bound to one qualified package; re-pinned and certificate-checked on every call.

    ``adapter.batch`` answers many requests in one isolated run under the same pin check, and
    certifies each answer separately; a refused answer is returned in its place, never hidden."""
    spec = CATALOG[function]

    def pinned(ctx):
        prov = ctx.manifest.provenance
        dist = mechanisms.installed(candidate.distribution)
        if dist is None or dist.version != prov["version"] \
                or mechanisms.digest(dist, candidate.digest_paths)[0] != prov["package_digest"]:
            raise CapabilityError("capability refused: package changed since qualification; quarantine required")
        return prov

    def settle(request, claim, prov):
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

    def adapter(params, ctx: InvocationContext):
        request = spec["normalize"](params)          # competence is enforced before the engine sees anything
        prov = pinned(ctx)
        [claim] = mechanisms.run(candidate, spec["runners"][candidate.runner], [request],
                                 location=prov["location"], version=prov["version"])
        return settle(request, claim, prov)

    def batch(params_list, ctx: InvocationContext) -> list:
        requests = []
        for params in params_list:
            try:
                requests.append(spec["normalize"](params))
            except CapabilityError as exc:
                requests.append(exc)
        prov = pinned(ctx)
        valid = [r for r in requests if not isinstance(r, Exception)]
        claims = iter(mechanisms.run(candidate, spec["runners"][candidate.runner], valid, location=prov["location"],
                                     version=prov["version"], cpu_seconds=60) if valid else [])
        out = []
        for request in requests:
            if isinstance(request, Exception):
                out.append(request)
                continue
            try:
                out.append(settle(request, next(claims), prov))
            except CapabilityError as exc:
                out.append(exc)
        return out

    adapter.batch = batch
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


FORMED = ("built:", "installed:", "composed:")   # providers Genesis formed, and therefore can re-form
FAULT_MARKERS = ("capability refused: built capability", "capability refused: installed binary changed",
                 "capability refused: package", "capability refused: composed")


RECOVERABLE = ("failed in service",)      # quarantine reasons that leave the capability's identity intact
RECOVERY_BASE = timedelta(minutes=15)    # first probe after a quarantine; doubles per failed probe and per fault
RECOVERY_CAP = timedelta(hours=24)
RECOVERY_MAX_FAILED_PROBES = 5
RECOVERY_MAX_QUARANTINES = 3            # more in-service quarantines than this is flapping: the founder decides
RECOVERED_BY = "recovery probe (sandbox, fresh frozen-oracle seed)"


class _ProbeView:
    """Registry view for one sandbox probe: the construction may call its pinned engine even while that
    engine is only VERIFIED. Nothing else differs; nothing is attached; service adapters never see it."""

    def __init__(self, registry, engine_id: str):
        self._registry, self._engine_id = registry, engine_id
        self.manifests, self.adapters, self.state = registry.manifests, registry.adapters, registry.state

    def usable(self, capability_id: str):
        if capability_id == self._engine_id and self.state.get(capability_id) in ("ATTACHED", "VERIFIED"):
            return True, "sandbox probe"
        return self._registry.usable(capability_id)


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

    def construction_engine(self, function: str):
        """The catalogued engine function a constructible function reduces to, else None."""
        found = recombine.chain(function, CATALOG)
        return found[1] if found else None

    def construction_ready(self, function: str) -> bool:
        """True once: the engine is attached and no construction over it was formed yet (none to wait on)."""
        engine_function = self.construction_engine(function)
        engine = self.find_attached(engine_function) if engine_function else None
        if engine is None:
            return False
        return not any(m.provider.startswith("composed:")
                       and m.provenance.get("target_capability_id") == engine.capability_id
                       for m in self.registry.by_function(function))

    # -- restart: rebuild acquired adapters from retained provenance -------------
    def restore(self, *, record: bool = True):
        """Re-register formed capabilities; ``record=False`` (independent appraisal over a read-only
        ledger) applies the same pin and digest checks but writes nothing."""
        self._recording = record
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
                    self._restore_note({"capability_id": cid, "state": "QUARANTINED",
                                                             "why": "built source missing or changed since verification"},
                                        key=[cid, "quarantine", origin["source_sha256"]])
                continue
            if origin.get("kind") == "package":
                self._restore_package(cid, manifest, origin, state)
                continue
            if origin.get("kind") == "composed":
                self._restore_composed(cid, manifest, origin, state)
                continue
            binary = manifest.binaries[0]
            candidate = Candidate(origin["binary_name"], tuple(origin["argv"]), origin["parse"])
            intact = Path(binary).exists() and hashlib.sha256(
                Path(binary).read_bytes()).hexdigest() == manifest.provenance.get("binary_sha256")
            self.registry.register(manifest, catalog_adapter(origin["function"], candidate, binary),
                                   state=state if intact else "QUARANTINED")
            if not intact and state != "QUARANTINED":
                self._restore_note({"capability_id": cid, "state": "QUARANTINED",
                                                         "why": "binary missing or changed since verification"},
                                    key=[cid, "quarantine", manifest.provenance.get("binary_sha256")])

    def _restore_note(self, payload, key):
        if getattr(self, "_recording", True):
            self.journal.record("capability.state", payload, key=key)

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
            self._restore_note({"capability_id": cid, "state": "QUARANTINED", "why": why},
                                key=[cid, "quarantine", manifest.provenance.get("package_digest"), why])

    def _restore_composed(self, cid, manifest, origin, state):
        """A constructed capability is trusted again only with the same reduction code over the same engine."""
        found = recombine.chain(origin["function"], CATALOG)
        why = None
        if found is None or [r.reduction_id for r in found[0]] != origin["chain"]:
            why = "the reduction chain no longer resolves as qualified"
        elif recombine.chain_digest(found[0]) != origin["chain_digest"]:
            why = "reduction code changed since qualification"
        elif origin["target_capability_id"] not in self.registry.manifests:
            why = "the engine it was qualified over is no longer registered"
        path = found[0] if found else []
        self.registry.register(manifest, recombine.composed_adapter(path, self.registry),
                               state="QUARANTINED" if why else state)
        if why and state != "QUARANTINED":
            self._restore_note({"capability_id": cid, "state": "QUARANTINED", "why": why},
                                key=[cid, "quarantine", origin["chain_digest"], why])

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
                                                 "mission_id": mission.mission_id, "incident": incident,
                                                 "at": iso(now)},
                            key=[capability_id, "quarantine", incident])
        engine_id = manifest.provenance.get("target_capability_id") if manifest.provider.startswith("composed:") \
            else None
        if engine_id and f"composed engine {engine_id} faulted" in failure \
                and self.registry.state.get(engine_id) == "ATTACHED":
            # The fault was the engine's, observed through the constructed capability: the engine is
            # quarantined with the same evidence, so re-forming acquires a different provider for it.
            self.registry.set_state(engine_id, "QUARANTINED")
            self.journal.record("capability.state", {"capability_id": engine_id, "state": "QUARANTINED",
                                                     "why": "failed in service inside " + capability_id + ": "
                                                            + failure[:300],
                                                     "by": "self-repair (repeated capability fault)",
                                                     "mission_id": mission.mission_id, "incident": incident,
                                                     "at": iso(now)},
                                key=[engine_id, "quarantine", incident])
        return self.resolve(mission=mission, function=manifest.function, now=now,
                            purpose=f"self-repair of {capability_id}",
                            repair={"capability_id": capability_id, "failure": failure[:300],
                                    "replay_path": params.get("path")})

    # -- recovery: a quarantined capability earns back eligibility, never authority ------------
    def _quarantines(self, capability_id: str) -> list[dict]:
        return [e.payload for e in self.journal.replay("capability.state")
                if e.payload["capability_id"] == capability_id and e.payload["state"] == "QUARANTINED"]

    def recover(self, now) -> list[dict]:
        """Half-open recovery for capabilities quarantined by an in-service fault.

        Donor mechanism (opossum 10.0.0, analysed with REA and read in source): after a fixed reset
        timeout the breaker lets the next *live* call through; success closes it, failure re-opens it.
        Mutations: the probe runs in the sandbox on a fresh frozen-oracle seed, never on live work;
        success restores eligibility (VERIFIED), never authority (ATTACHED); the wait doubles with each
        failed probe and each prior quarantine; flapping stops recovery for the founder to decide;
        engines are probed before the constructions that depend on them. Identity-changing quarantines
        (pins, code, missing source) are never probed: the same identity cannot be re-earned."""
        results = []
        formed = [m for m in self.registry.manifests.values()
                  if is_formed(m) and self.registry.state.get(m.capability_id) == "QUARANTINED"]
        if not formed:                                     # every replay re-verifies the whole ledger chain:
            return results                                 # a healthy body pays nothing for recovery each tick
        probes = [e.payload for e in self.journal.replay("capability.probe")]
        stopped = {(e.payload["capability_id"], e.payload["incident"])
                   for e in self.journal.replay("capability.recovery_stopped")}
        for manifest in sorted(formed, key=lambda m: (m.provider.startswith("composed:"), m.capability_id)):
            cid = manifest.capability_id
            if self.registry.state.get(cid) != "QUARANTINED":
                continue
            history = self._quarantines(cid)
            last = history[-1] if history else {}
            if not str(last.get("why", "")).startswith(RECOVERABLE) or not last.get("incident"):
                continue                                   # identity changed, or quarantined before recovery existed
            incident = last["incident"]
            if (cid, incident) in stopped:
                continue
            failed = [p for p in probes if p["capability_id"] == cid and p["incident"] == incident and not p["passed"]]
            faults = [q for q in history if str(q.get("why", "")).startswith(RECOVERABLE)]
            why_stop = ("flapping: quarantined in service %d times" % len(faults)
                        if len(faults) > RECOVERY_MAX_QUARANTINES
                        else "%d recovery probes failed" % len(failed) if len(failed) >= RECOVERY_MAX_FAILED_PROBES
                        else None)
            if why_stop:
                self.journal.record("capability.recovery_stopped", {
                    "capability_id": cid, "incident": incident, "why": why_stop,
                    "next": "the founder decides: re-attach, detach, or replace", "at": iso(now)},
                    key=[cid, incident, "recovery-stopped"])
                results.append({"capability_id": cid, "result": "stopped", "why": why_stop})
                continue
            wait = min(RECOVERY_BASE * 2 ** (len(failed) + len(faults) - 1), RECOVERY_CAP)
            since = datetime.fromisoformat(last["at"].replace("Z", "+00:00"))
            if failed:
                since = max(since, datetime.fromisoformat(failed[-1]["at"].replace("Z", "+00:00")))
            if now < since + wait:
                continue
            attempt = len(failed) + 1
            seed = int(sha256_json({"probe": cid, "incident": incident, "attempt": attempt})[7:15], 16)
            outcome = self._probe(manifest, seed)
            if outcome is None:                            # a dependency has not recovered yet: not a failure
                results.append({"capability_id": cid, "result": "waiting on its engine"})
                continue
            passed, report = outcome
            self.journal.record("capability.probe", {
                "capability_id": cid, "incident": incident, "attempt": attempt, "passed": passed, "report": report,
                "seed": seed, "waited_seconds": int(wait.total_seconds()), "at": iso(now),
                "mechanism": "half-open probe in the sandbox on a fresh frozen-oracle seed (opossum-derived, mutated)"},
                key=[cid, incident, attempt])
            if passed:
                self.registry.set_state(cid, "VERIFIED")
                self.journal.record("capability.state", {
                    "capability_id": cid, "state": "VERIFIED", "by": RECOVERED_BY, "incident": incident,
                    "at": iso(now), "authority": "eligibility only; attach still needs the founder or a signed "
                                                 "mission scope"}, key=[cid, "recovered", incident])
            results.append({"capability_id": cid, "result": "recovered" if passed else "probe failed",
                            "attempt": attempt})
        return results

    def _probe(self, manifest, seed: int):
        """The capability's own qualification, re-run in isolation. None: a dependency is not ready yet."""
        origin = next((e.payload["origin"] for e in reversed(self.journal.replay("capability.registered"))
                       if e.payload["manifest"]["capability_id"] == manifest.capability_id), {})
        prov = manifest.provenance
        if origin.get("kind") == "package":
            candidate = next((c for c in CATALOG.get(origin["function"], {}).get("candidates", ())
                              if isinstance(c, PackageCandidate) and c.runner == origin["runner"]), None)
            dist = mechanisms.installed(origin["distribution"]) if candidate else None
            if dist is None or dist.version != prov.get("version") \
                    or mechanisms.digest(dist, candidate.digest_paths)[0] != prov.get("package_digest"):
                return False, {"identity": "the pinned package is missing or changed; this identity cannot recover"}
            return qualify_package(origin["function"], candidate, mechanisms.card(candidate, origin["function"], dist),
                                   seed)
        if origin.get("kind") == "composed":
            found = recombine.chain(origin["function"], CATALOG)
            if found is None or recombine.chain_digest(found[0]) != origin["chain_digest"]:
                return False, {"identity": "the reduction code changed; this identity cannot recover"}
            engine_id = origin["target_capability_id"]
            if self.registry.state.get(engine_id) not in ("ATTACHED", "VERIFIED"):
                return None
            view = _ProbeView(self.registry, engine_id)    # the probe may call its own engine; service may not
            return recombine.qualify(found[0], recombine.composed_adapter(found[0], view), manifest, seed)
        return False, {"identity": "no recovery probe for this kind of formed capability yet"}

    def recovered_for(self, function: str) -> list[str]:
        """Recovery keys (capability@incident) of capabilities this function can be re-admitted through."""
        targets = {m.capability_id for m in self.registry.by_function(function)}
        engine = self.construction_engine(function)
        if engine:
            targets |= {m.capability_id for m in self.registry.by_function(engine)}
        if not any(self.registry.state.get(cid) == "VERIFIED" for cid in targets):
            return []                                      # nothing re-admittable; skip the full-ledger replay
        return [f"{e.payload['capability_id']}@{e.payload['incident']}" for e in self.journal.replay("capability.state")
                if e.payload["capability_id"] in targets and e.payload.get("by") == RECOVERED_BY
                and self.registry.state.get(e.payload["capability_id"]) == "VERIFIED"]

    def _attach_dependency(self, mission, manifest, dependent: str, now) -> bool:
        """Attach the exact engine a construction is pinned to, under the same signed scope, or ask."""
        allowed = (mission.spec.get("auto_attach", {}).get("max_consequence_class") == "read_only"
                   and manifest.consequence_class == "read_only"
                   and mission.cone._capability_inside(manifest.capability_id))
        if not allowed:
            return False
        self.registry.set_state(manifest.capability_id, "ATTACHED")
        self.journal.record("capability.state", {"capability_id": manifest.capability_id, "state": "ATTACHED",
                                                 "by": "founder-signed mission auto_attach (read_only), engine of "
                                                       + dependent, "mission_id": mission.mission_id,
                                                 "at": iso(now)},
                            key=[manifest.capability_id, "attached", mission.mission_id, dependent])
        return True

    def resolve(self, *, mission, function: str, purpose: str, now, repair: dict | None = None):
        found = self.find_attached(function)
        if found:
            return found
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
        reduction = recombine.REDUCTIONS.get(function)
        if spec is None and reduction is not None:
            acceptance = {"oracle": f"reduction:{reduction.reduction_id}", "seed": seed,
                          "vector_digest": sha256_json(reduction.oracle(seed))}
        elif spec is None and contract is not None:
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
            elif spec is None and reduction is not None:
                opened["search_order"] = ["attached", "verified_detached", "constructed", "builder", "founder"]
            if repair is not None:
                opened["repair"] = repair
            self.journal.record("deficit.opened", opened, key=deficit_id)

        # 2. registered but detached
        for manifest in self.registry.by_function(function):
            if self.registry.state[manifest.capability_id] == "VERIFIED":
                engine_id = manifest.provenance.get("target_capability_id") \
                    if manifest.provider.startswith("composed:") else None
                if engine_id and self.registry.state.get(engine_id) != "ATTACHED":
                    engine = self.registry.manifests.get(engine_id)
                    if engine is None or self.registry.state.get(engine_id) != "VERIFIED" \
                            or not self._attach_dependency(mission, engine, manifest.capability_id, now):
                        self._route(deficit_id, "verified_detached", f"its engine {engine_id} is not attached",
                                    manifest.capability_id)
                        continue
                self._route(deficit_id, "verified_detached", "found", manifest.capability_id)
                return self._attach(mission, manifest, deficit_id, now)
        self._route(deficit_id, "verified_detached", "none", None)

        if spec is None and reduction is not None:
            found = self._recombine_route(mission, function, deficit_id, seed, repair, now)
            if found is not False:
                return found
            return self._builder_route(mission, function, deficit_id, now, contract, repair)

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
            if self._recorded_qualification(deficit_id, manifest.capability_id) is not None:
                self._route(deficit_id, "installed_software", f"{candidate.binary_name} was verified earlier on this "
                            "deficit (recorded; not re-run)", manifest.capability_id)
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

    def _package_route(self, mission, function, spec, deficit_id, seed, repair, now):
        """Existing project mechanisms first, then installed open-source packages (DEPEND).

        Returns the attached manifest, None when one awaits the founder's attach, or False
        when no package qualified (the caller continues to the builder route)."""
        for cid, why_not in spec.get("project", ()):
            self._route(deficit_id, "existing_project", f"{cid}: {why_not}", cid)
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
            if repair and repair.get("capability_id") == manifest.capability_id:
                self._route(deficit_id, "installed_package", "this package failed in service; a different provider is "
                                                             "preferred (the founder may re-attach it)",
                            manifest.capability_id)
                continue
            prior = self._recorded_qualification(deficit_id, manifest.capability_id, card["package_digest"])
            if prior is not None:
                self._route(deficit_id, "installed_package", f"{candidate.distribution} "
                            f"{'qualified' if prior['passed'] else 'failed qualification'} earlier on this deficit "
                            "(recorded; not re-run)", manifest.capability_id)
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

    def _recombine_route(self, mission, function, deficit_id, seed, repair, now):
        """Construct the function by certified reduction onto an engine GREG already trusts (RECOMBINE).

        Returns the attached manifest, None while it (or its engine) awaits the founder's attach,
        or False when no constructed capability qualified (the caller continues to the builder)."""
        found = recombine.chain(function, CATALOG)
        if found is None:
            self._route(deficit_id, "constructed", "no reduction chain ends at a catalogued engine", None)
            return False
        path, engine_function = found
        self._route(deficit_id, "constructed", "chain " + " -> ".join([r.function for r in path] + [engine_function]),
                    None)
        engine = self.find_attached(engine_function)
        if engine is None:
            # The engine is itself a deficit, searched by the same ladder and recorded with this lineage.
            engine = self.resolve(mission=mission, function=engine_function, now=now,
                                  purpose=f"engine for constructed {function} ({deficit_id})")
        if engine is None:
            self._route(deficit_id, "constructed", f"engine {engine_function} is not attached yet", None)
            return None
        manifest = self._composed_manifest(function, path, engine, deficit_id)
        if self.registry.state.get(manifest.capability_id) == "DETACHED":
            self._route(deficit_id, "constructed", "founder-detached; explicit attach required", manifest.capability_id)
            return False
        if repair and repair.get("capability_id") == manifest.capability_id:
            self._route(deficit_id, "constructed", "this construction failed in service; a different engine is "
                                                   "required (the founder may re-attach it)", manifest.capability_id)
            return False
        prior = self._recorded_qualification(deficit_id, manifest.capability_id)
        if prior is not None:
            self._route(deficit_id, "constructed", f"{'qualified' if prior['passed'] else 'failed qualification'} "
                        "earlier on this deficit (recorded; not re-run)", manifest.capability_id)
            return False
        adapter = recombine.composed_adapter(path, self.registry)
        passed, report = recombine.qualify(path, adapter, manifest, seed)
        self.journal.record("genesis.verified", {"deficit_id": deficit_id, "capability_id": manifest.capability_id,
                                                 "passed": passed, "report": report,
                                                 "mechanism": [r.card | {"reduction_id": r.reduction_id}
                                                               for r in path],
                                                 "verifier": "frozen brute-force oracle of the constructed function "
                                                             "and GREG's problem-level certificate, independent of "
                                                             "the engine"},
                            key=[deficit_id, manifest.capability_id, manifest.provenance["chain_digest"]])
        if not passed:
            self._route(deficit_id, "constructed", "failed qualification", manifest.capability_id)
            return False
        manifest = self._composed_manifest(function, path, engine, deficit_id, report)
        self.registry.register(manifest, adapter, state="VERIFIED")
        self.journal.record("capability.registered", {
            "manifest": manifest.to_dict(), "state": "VERIFIED", "deficit_id": deficit_id,
            "origin": {"kind": "composed", "function": function, "chain": [r.reduction_id for r in path],
                       "chain_digest": manifest.provenance["chain_digest"],
                       "target_capability_id": engine.capability_id}},
            key=[manifest.capability_id, manifest.digest()])
        self._route(deficit_id, "constructed", "constructed and verified", manifest.capability_id)
        return self._attach(mission, manifest, deficit_id, now)

    def _composed_manifest(self, function, path, engine, deficit_id, report=None) -> CapabilityManifest:
        head, digest = path[0], recombine.chain_digest(path)
        if engine.consequence_class != "read_only":
            raise CapabilityError("a constructed capability may only compose read-only engines")
        return CapabilityManifest(
            capability_id=f"composed.{function}.{engine.capability_id.rsplit('.', 1)[-1]}.{digest[:10]}",
            version="1.0.0", provider="composed:" + "+".join(r.reduction_id for r in path), function=function,
            description=head.description[:300], route="internal", consequence_class="read_only", inputs=head.inputs,
            outputs={"certified": "bool", "certificate": "dict"}, target_prefix="cognition:", filesystem="none",
            retry_safe=True, tests=(f"frozen-oracle:{function}", "certificate:every-call"),
            strengthens=("capability_formation", "proof", "compounding"),
            provenance={"mode": "RECOMBINE", "chain": [r.reduction_id for r in path], "chain_digest": digest,
                        "source_digests": {r.reduction_id: recombine.source_digest(r) for r in path},
                        "target_capability_id": engine.capability_id, "target_manifest_digest": engine.digest(),
                        "engine_function": engine.function, "deficit_id": deficit_id,
                        "baseline": head.baseline, "cards": [r.card for r in path],
                        "builder": "none: constructed by certified reduction from GREG's reduction library",
                        "license": "GREG code; the engine keeps its own license (see its manifest)",
                        **({"qualification": report} if report else {})})

    def _recorded_qualification(self, deficit_id: str, capability_id: str, digest: str | None = None):
        """A qualification already recorded on this deficit is reused, never re-run: the ledger holds one
        fact per (deficit, candidate), and re-running it would only repeat the same evidence."""
        for event in reversed(self.journal.replay("genesis.verified")):
            p = event.payload
            if p["deficit_id"] == deficit_id and p["capability_id"] == capability_id and \
                    (digest is None or (p.get("mechanism") or {}).get("package_digest") == digest):
                return p
        return None

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
        # Founder-signed pre-authorization only: read-only, and inside the cone.
        allowed = (mission.spec.get("auto_attach", {}).get("max_consequence_class") == "read_only"
                   and manifest.consequence_class == "read_only"
                   and mission.cone._capability_inside(manifest.capability_id))
        if not allowed:
            self.journal.record("deficit.awaiting_attach", {"deficit_id": deficit_id,
                                                            "capability_id": manifest.capability_id,
                                                            "why": "mission scope does not pre-authorize this attach"},
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
