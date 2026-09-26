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
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import random
import sys
import tempfile

from greg.capabilities import (CapabilityError, CapabilityManifest, InvocationContext, installed_binary,
                               run_isolated)
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


class Genesis:
    """The resourceful capability-formation loop, recorded on the canonical spine."""

    def __init__(self, *, journal: Journal, registry, workspace_root: Path, builder=None):
        self.journal, self.registry = journal, registry
        self.workspace_root, self.builder = Path(workspace_root), builder

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
            if event.type == "greg.capability.registered" and data["manifest"]["provider"].startswith("installed:"):
                states[data["manifest"]["capability_id"]] = (data, states.get(data["manifest"]["capability_id"], (None, "VERIFIED"))[1])
            elif event.type == "greg.capability.state" and data["capability_id"] in states:
                states[data["capability_id"]] = (states[data["capability_id"]][0], data["state"])
        for cid, (data, state) in states.items():
            manifest = CapabilityManifest.from_dict(data["manifest"])
            origin = data["origin"]
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
    def resolve(self, *, mission, function: str, purpose: str, now):
        found = self.find_attached(function)
        if found:
            return found
        deficit_id = "deficit-" + sha256_json({"mission": mission.mission_id, "function": function})[7:31]
        spec = CATALOG.get(function)
        seed = int(sha256_json({"deficit": deficit_id})[7:15], 16)
        acceptance = {"oracle": function if spec else None, "seed": seed,
                      "vector_digest": sha256_json([{k: (v.hex() if isinstance(v, bytes) else v)
                                                     for k, v in c.items()} for c in spec["oracle"](seed)])
                      if spec else None}
        self.journal.record("deficit.opened", {
            "deficit_id": deficit_id, "mission_id": mission.mission_id, "function": function,
            "purpose": purpose, "acceptance": acceptance, "at": iso(now),
            "search_order": ["attached", "verified_detached", "installed_software", "builder", "founder"]},
            key=deficit_id)

        # 2. registered but detached
        for manifest in self.registry.by_function(function):
            if self.registry.state[manifest.capability_id] == "VERIFIED":
                self._route(deficit_id, "verified_detached", "found", manifest.capability_id)
                return self._attach(mission, manifest, deficit_id, now)
        self._route(deficit_id, "verified_detached", "none", None)

        if spec is None:
            self._route(deficit_id, "installed_software", "no frozen oracle for this function; cannot verify",
                        None)
            return self._builder_route(mission, function, deficit_id, now)

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
        return self._builder_route(mission, function, deficit_id, now)

    def _route(self, deficit_id, route, result, capability_id):
        self.journal.record("genesis.route", {"deficit_id": deficit_id, "route": route, "result": result,
                                              "capability_id": capability_id},
                            key=[deficit_id, route, result, capability_id])

    def _builder_route(self, mission, function, deficit_id, now):
        if self.builder is None:
            self._route(deficit_id, "builder", "no builder attached (coding agent/human/model not connected)", None)
            self._route(deficit_id, "founder", "escalated", None)
            return None
        result = self.builder.build(function=function, deficit_id=deficit_id)
        self._route(deficit_id, "builder", f"builder {getattr(self.builder, 'identity', 'unknown')} returned "
                    f"{'a candidate' if result else 'nothing'}", None)
        self._route(deficit_id, "founder", "escalated", None)
        return None

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
                            key=[manifest.capability_id, "attached", mission.mission_id])
        self.journal.record("deficit.resolved", {"deficit_id": deficit_id, "capability_id": manifest.capability_id,
                                                 "mission_id": mission.mission_id, "resume": "original mission",
                                                 "at": iso(now)}, key=[deficit_id, "resolved"])
        return manifest
