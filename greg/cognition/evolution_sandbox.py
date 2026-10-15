"""P8 candidate sandbox: run one candidate configuration on problem INPUTS only, then exit.

The parent (``greg/cognition/evolution.py``) builds every request itself; a candidate is a validated
configuration (data), never code. This process parses the request, imports the one reviewed method its
target names from the TARGETS allow-list, then irreversibly confines itself with Landlock before it runs
anything on the problems, so nothing it runs can open repository files - in particular the evaluator's real
outcomes, which never enter this process at all. Output: outputs per problem id, with {"confined": ...}
recorded so the parent can refuse unconfined runs where confinement is required.

The parent compares the code this process executed with its pre-registered closure, so every repository module
is hashed from the exact bytes the import system compiled: repository bytecode is never read (a ``.pyc`` in
``__pycache__`` would run instead of the hashed source), and no file is re-read after its import.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import json
import os
from pathlib import Path
import resource
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
_EXECUTED: dict[str, str] = {}
_READ = importlib.machinery.SourceFileLoader.get_data


def _get_data(loader, path):
    """Repository source is recorded as the bytes compiled; repository bytecode is refused, which makes the
    import system compile from those bytes (``SourceLoader.get_code`` treats OSError as "no bytecode")."""
    resolved = Path(path).resolve()
    inside = ROOT in resolved.parents
    if inside and resolved.suffix == ".pyc":
        raise OSError("repository bytecode is never executed in the P8 sandbox")
    data = _READ(loader, path)
    if inside and resolved.suffix == ".py":
        _EXECUTED[resolved.relative_to(ROOT).as_posix()] = "sha256:" + hashlib.sha256(data).hexdigest()
    return data


def _prepare():
    """Before this process imports any repository module: hash what it compiles, never read repository
    bytecode, write none, and keep one thread (Landlock confines the calling thread only, so a BLAS pool an
    import starts before confine() would stay outside the domain; confine() refuses a multi-threaded process)."""
    sys.dont_write_bytecode = True
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"
    importlib.machinery.SourceFileLoader.get_data = _get_data
    _EXECUTED[Path(__file__).resolve().relative_to(ROOT).as_posix()] = (
        "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    sys.path[:] = search_path(sys.path)


def search_path(path: list) -> list:
    """The repository after the standard library and before installed packages: a file at the repository root
    named like a standard module (``platform.py``) never shadows it, and the repository's own packages still
    come before any installed package of the same name."""
    installed = next((i for i, p in enumerate(path) if "site-packages" in p or "dist-packages" in p), len(path))
    return [*path[:installed], str(ROOT), *path[installed:]]


# The only code a cycle can run: reviewed modules and functions, named by the trusted parent's target, with
# the runtime modules each imports lazily. Those are imported BEFORE confinement so the shared libraries they
# map (numpy's libstdc++ on hosts whose Python lives outside /usr) are granted as already-loaded files.
TARGETS = {"forecast_quantile": ("greg.cognition.genomes.forecasting", "solve_with", ()),
           "immune_detect": ("greg.cognition.genomes.collective", "immune_solve_with",
                             ("numpy", "numpy.linalg", "numpy.random")),
           "constraint_release": ("greg.cognition.genomes.developmental", "constraint_release_solve_with", ())}


def executed() -> dict:
    """Every repository file this process executed, by the digest of the bytes it ran. A module under the
    repository that did not come through the hashed source loader (an extension module, another loader) is
    reported UNHASHED, which the parent refuses."""
    out = dict(_EXECUTED)
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if not path:
            continue
        resolved = Path(path).resolve()
        if ROOT in resolved.parents:
            out.setdefault(resolved.relative_to(ROOT).as_posix(), "UNHASHED")
    return dict(sorted(out.items()))


def main():
    from greg.cognition.genomes.contract import GenomeError
    from greg import isolation
    request = json.loads(sys.stdin.read(64 * 1024 * 1024))
    if request.get("target") not in TARGETS:
        print(json.dumps({"confined": None, "error": "UNKNOWN_TARGET"}))
        return
    module, function, runtime = TARGETS[request["target"]]
    method = getattr(importlib.import_module(module), function)      # imported BEFORE confinement
    for name in runtime:
        importlib.import_module(name)                                 # lazily used, so preloaded here too
    # What this process executed, recorded before confinement and before any problem runs: the parent compares
    # it with its pre-registered closure, so an on-disk edit of any executed module cannot run unnoticed.
    loaded = executed()
    imported = {"module": module, "sha256": loaded.get(module.replace(".", "/") + ".py")}
    resource.setrlimit(resource.RLIMIT_CPU, (120, 121))
    scratch = tempfile.mkdtemp(prefix="greg-p8-")
    confined = None
    if request.get("confine", True):
        try:
            # everything this process runs is already imported: not even the repository's listing is granted
            confined = isolation.confine(scratch, [], list_code=False)
        except isolation.IsolationError as exc:
            print(json.dumps({"confined": None, "error": f"CONFINEMENT_UNAVAILABLE: {exc}", "imported": imported,
                              "loaded": loaded}))
            return
    probe = request.get("probe_read")            # test-only: report whether a path is readable, never its bytes
    probe_result = None
    if probe:
        try:
            with open(probe, "rb") as fh:
                fh.read(1)
            probe_result = "READ"
        except OSError as exc:
            probe_result = f"DENIED:{type(exc).__name__}"
    outputs = {}
    for problem in request["problems"]:
        try:
            out = method(request["config"], problem["data"])
            outputs[problem["id"]] = {"output": out["output"], "certificate": out["certificate"]}
        except Exception as exc:             # recorded per problem (a TypeError once aborted a whole cycle)
            kind = "GenomeError" if isinstance(exc, GenomeError) else type(exc).__name__
            outputs[problem["id"]] = {"error": f"{kind}: {str(exc)[:160]}"}
    print(json.dumps({"confined": confined, "probe": probe_result, "imported": imported, "loaded": loaded,
                      "outputs": outputs}))


if __name__ == "__main__":
    _prepare()
    main()
