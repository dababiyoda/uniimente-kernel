"""Capability Genesis: canonical UNIIMENTE morphogenesis as a working mechanism.

When a mission needs a function GREG does not have, it does not stop and it does
not pretend. It opens a CapabilityDeficit, freezes the acceptance test *before*
any candidate exists, then searches reality in resourcefulness order:

    1. an ATTACHED capability with that function            (use what exists)
    2. a VERIFIED but detached capability                   (re-attach)
    3. installed commodity software on this body            (acquire)
    4. a pluggable builder (coding agent / human / model)   (build the residual)
    5. founder escalation                                   (ask, wait)

Every candidate is untrusted. It runs with no network, a scrubbed environment and
a timeout, and is judged by an independent oracle that the candidate never sees.
A passing candidate is registered with provenance (binary path and content hash,
version string, builder identity) as VERIFIED. Attachment still needs either a
founder CAPABILITY_ATTACH command or a founder-signed mission ``auto_attach``
limited to read-only functions. The original mission then resumes; genesis
completion never closes the mission.

Self-repair: a formed capability that later fails in service (its built source or
binary changed, or it raises on live input) is quarantined with the failure as
evidence, and the same search runs again as a new deficit generation. A rebuilt
candidate must pass the same frozen oracle *and* run cleanly on the live input
that broke its predecessor (replayed locally in isolation; never sent to a model).
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile

from greg.capabilities import (CapabilityError, CapabilityManifest, InvocationContext, installed_binary,
                               run_isolated)
from greg import builders
from greg.journal import Journal, iso
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
}


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


FORMED = ("built:", "installed:")      # providers Genesis formed, and therefore can re-form
FAULT_MARKERS = ("capability refused: built capability", "capability refused: installed binary changed")


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
                path = self.store / f"{origin['source_sha256']}.py"
                intact = path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == origin["source_sha256"]
                self.registry.register(manifest, builders.built_adapter(origin["contract"], path, origin["source_sha256"]),
                                       state=state if intact else "QUARANTINED")
                if not intact and state != "QUARANTINED":
                    self.journal.record("capability.state", {"capability_id": cid, "state": "QUARANTINED",
                                                             "why": "built source missing or changed since verification"},
                                        key=[cid, "quarantine", origin["source_sha256"]])
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

        # 3. installed commodity software
        for candidate in spec["candidates"]:
            binary = installed_binary(candidate.binary_name)
            if binary is None:
                self._route(deficit_id, "installed_software", f"{candidate.binary_name} not installed", None)
                continue
            manifest = self._manifest_for(function, candidate, binary, deficit_id)
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
                "cost_usd": built.get("cost_usd"), "sees": "description, signature, public examples only"},
                key=[deficit_id, attempt, digest])
            problems = builders.screen(source)
            path = self.store / f"{digest}.py"
            if not problems and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                # stored bytes no longer match their name: keep them as evidence, restore the verified bytes
                actual = hashlib.sha256(path.read_bytes()).hexdigest()
                path.rename(path.with_name(f"{path.name}.unverified-{actual[:16]}"))
            if not problems and not path.exists():
                path.write_text(source)
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
