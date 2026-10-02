"""Open-source mechanism supply: qualify an installed package before GREG depends on it.

Founder correction of 2026-10-01 (INTENT-20261001-open-source-mechanism-harvest, draft #144,
comment on #143): open-source code is construction supply, not only comparison material.
This module is the DEPEND mode of that correction for packages already installed on the
body. Capability Genesis uses it when a mission needs a function GREG lacks:

    deficit -> installed distribution found -> Mechanism Card (upstream, version, license,
    content digest, shared dependencies, declared competence) -> frozen oracle in a
    no-network interpreter -> VERIFIED -> attach only by founder command or signed scope

It never installs, downloads, upgrades or imports a candidate into the body process. The
candidate runs a fixed GREG-written runner in a separate isolated interpreter, and its
output is accepted only after GREG's own certificate checks it (greg/cortex_engines/network.py).
A package that is merely present gains nothing: building != installation != attachment !=
authority.

The digest pins the installer's RECORD and the bytes of the files that implement the
mechanism. A change to another file of the distribution without a change to RECORD is not
detected; the limit is stated on every card.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import tempfile

from greg.capabilities import CapabilityError, run_isolated

REUSE_MODES = ("DISCOVER", "DEPEND", "VENDOR-SLICE", "FORK/SUBTREE", "RECOMBINE")
MAX_OUTPUT = 4 * 1024 * 1024


@dataclass(frozen=True)
class PackageCandidate:
    """One installed open-source distribution that can realize a function."""
    distribution: str          # importlib.metadata name
    module: str                # the import the runner performs
    runner: str                # key into the function's runner table (GREG-written code)
    digest_paths: tuple        # path prefixes inside the distribution that implement the mechanism
    primitive: str             # what the upstream supplies, in one line
    competence: str            # limits GREG enforces before the package sees any input
    common_mode: tuple = ()    # upstream distributions this candidate shares with others


def installed(name: str):
    """The installed distribution visible to this interpreter, or None. Never installs."""
    try:
        return importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def license_of(dist) -> str:
    meta = dist.metadata
    expression = meta.get("License-Expression")
    if expression:
        return expression
    classifiers = [c.split("::")[-1].strip() for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")]
    if classifiers:
        return "; ".join(classifiers) + " (trove classifier)"
    text = (meta.get("License") or "").strip().splitlines()
    return f"{text[0][:120]} (license text; no SPDX expression)" if text else "UNDECLARED"


def upstream_of(dist) -> dict:
    urls = {}
    for entry in dist.metadata.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        urls[label.strip().lower()] = url.strip()
    if dist.metadata.get("Home-page"):
        urls.setdefault("homepage", dist.metadata["Home-page"])
    source = next((urls[k] for k in ("source", "source code", "repository", "code") if k in urls), None)
    return {"source": source or urls.get("homepage"), "urls": dict(sorted(urls.items()))}


def digest(dist, prefixes: tuple) -> tuple[str, int]:
    """sha256 over the installer's RECORD and the bytes of the mechanism's files."""
    record = dist.read_text("RECORD")
    if record is None:
        raise CapabilityError(f"{dist.metadata['Name']} has no RECORD; its files cannot be pinned")
    h = hashlib.sha256(record.encode())
    count = 0
    for f in sorted(dist.files or (), key=str):
        name = str(f)
        if name.endswith(".pyc") or not name.startswith(prefixes):
            continue
        try:
            data = Path(f.locate()).read_bytes()
        except OSError as exc:
            raise CapabilityError(f"{name} listed in RECORD is unreadable: {exc}") from exc
        h.update(name.encode() + b"\0" + hashlib.sha256(data).digest())
        count += 1
    if not count:
        raise CapabilityError(f"no files under {prefixes} in {dist.metadata['Name']}; nothing to pin")
    return h.hexdigest(), count


def shared(dist_names: tuple) -> list[dict]:
    """Version and RECORD digest of each common-mode dependency (a change shows at restart)."""
    out = []
    for name in dist_names:
        dep = installed(name)
        record = dep.read_text("RECORD") if dep else None
        out.append({"distribution": name, "version": dep.version if dep else None,
                    "record_sha256": hashlib.sha256(record.encode()).hexdigest() if record else None})
    return out


def card(candidate: PackageCandidate, function: str, dist) -> dict:
    """The Mechanism Card: what is reused, from where, under which terms and limits."""
    pinned, files = digest(dist, candidate.digest_paths)
    return {"function": function, "mode": "DEPEND", "distribution": dist.metadata["Name"],
            "version": dist.version, "license": license_of(dist), "upstream": upstream_of(dist),
            "module": candidate.module, "location": str(Path(dist.locate_file("")).resolve()),
            "package_digest": pinned, "pinned_files": files, "pinned_paths": list(candidate.digest_paths),
            "primitive": candidate.primitive, "competence": candidate.competence,
            "common_mode": shared(candidate.common_mode),
            "runtime": "fixed GREG runner in a separate no-network interpreter; never imported by the body",
            "acquisition": "already installed on this body; GREG did not download or install it",
            "limits": "a change to an unpinned file of the distribution without a RECORD change is not detected; "
                      "license read from installed metadata, not from a legal review"}


RUNNER_PREAMBLE = r'''
import json, resource, sys
seconds = int(sys.argv[2])
resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds + 1))
if sys.platform != "darwin":
    resource.setrlimit(resource.RLIMIT_AS, (3 * 1024**3, 3 * 1024**3))
request = json.load(open(sys.argv[1]))
'''

RUNNER_EPILOGUE = r'''
import importlib.metadata, time
results = []
for item in request["batch"]:
    started = time.perf_counter()
    try:
        results.append({"result": solve(item), "seconds": time.perf_counter() - started})
    except Exception as exc:
        results.append({"error": f"{type(exc).__name__}: {exc}"[:300]})
print(json.dumps({"module_file": MODULE.__file__, "version": importlib.metadata.version(DISTRIBUTION),
                  "results": results}))
'''


def run(candidate: PackageCandidate, source: str, requests: list, *, location: str, version: str,
        cpu_seconds: int = 20) -> list[dict]:
    """Run the fixed runner for one candidate on a batch of requests, isolated.

    Returns one entry per request: {"result", "seconds"} or {"error"}. The import location
    and version are checked against the qualified ones before any result is returned."""
    program = (RUNNER_PREAMBLE + f"import {candidate.module} as MODULE\nDISTRIBUTION = {candidate.distribution!r}\n"
               + source + RUNNER_EPILOGUE)
    with tempfile.TemporaryDirectory(prefix="greg-package-") as tmp:
        path = Path(tmp) / "request.json"
        path.write_text(json.dumps({"batch": requests}))
        try:
            proc = run_isolated([sys.executable, "-I", "-c", program, str(path), str(cpu_seconds)], cwd=Path(tmp),
                                timeout=cpu_seconds + 20,
                                extra_env={"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        except Exception as exc:          # a timeout or refused isolation is a fault of this route
            raise CapabilityError(f"capability refused: package runner for {candidate.distribution} "
                                  f"did not complete ({type(exc).__name__})") from exc
    if proc.returncode:
        raise CapabilityError(f"capability refused: package runner for {candidate.distribution} exited "
                              f"{proc.returncode}: {proc.stderr.decode('utf-8', 'replace')[-240:]}")
    if len(proc.stdout) > MAX_OUTPUT:
        raise CapabilityError(f"capability refused: package runner for {candidate.distribution} output too large")
    try:
        claim = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise CapabilityError(f"capability refused: package runner for {candidate.distribution} "
                              "produced unreadable output") from exc
    root = Path(location).resolve()
    module_file = Path(claim.get("module_file") or "/").resolve()
    if root not in module_file.parents:
        raise CapabilityError(f"capability refused: package {candidate.module} was imported from {module_file}, "
                              f"not from the qualified location {root}")
    if claim.get("version") != version or not isinstance(claim.get("results"), list) \
            or len(claim["results"]) != len(requests):
        raise CapabilityError(f"capability refused: package {candidate.distribution} reported version "
                              f"{claim.get('version')!r} (qualified {version}) or the wrong number of results")
    return claim["results"]
