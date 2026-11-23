"""Instance extraction for the natural dependency-control-point family (NATURAL inputs: this repository's history).

An instance is ``(commit, source module S, target module T)`` on the repository-internal Python import graph at a
committed revision, read with ``git ls-tree`` / ``git cat-file`` only (no checkout, no network, no execution of
the code being read). The question asked of every arm is the set of CONTROL POINTS between S and T: a minimum set
of intermediate modules whose removal leaves no import path from S to T (a minimum S-T vertex cut). Its size is
the number of modules that must all fail before the dependency is severed; a cut of size 1 is a single point of
failure.

Graph construction (declared, fixed):

* nodes are ``*.py`` files tracked at the commit outside ``tests/``; ``a/b/c.py`` is module ``a.b.c`` and
  ``a/b/__init__.py`` is ``a.b``;
* an edge ``A -> B`` exists when A's source contains, anywhere (lazy, function-level imports included), ``import
  X`` or ``from X import n`` that resolves to a repository module B != A. ``import a.b.c`` resolves to the deepest
  existing prefix; ``from a.b import n`` resolves to ``a.b.n`` when that is a module, else ``a.b``; relative imports
  resolve against A's package. Parent-package ``__init__`` execution is NOT modelled as an edge;
* a file that does not parse at that commit contributes a node with no out-edges and is counted.

Selection rule (declared before any held-out instance exists; see PREREGISTRATION.md):

* commits: the first-parent history of the base commit, every ``COMMIT_STRIDE``-th first-parent commit starting at
  the base, at most ``MAX_COMMITS``;
* sources: ``SOURCES``, GREG's operating entry points (CLI, mission engine, body, Goal Gravity, remote, console),
  each when present at the commit;
* targets: every module T reachable from S, not S itself, and not imported by S directly (a direct edge has no
  vertex cut). Each instance carries ``target_class``: ``organ_or_evidence`` when T's top-level package is in
  ``TARGET_ROOTS`` (organs, adapters, evidence/provenance writers, events) or T is one of ``TARGET_MODULES``
  (GREG's organ bridges and evidence writers), else ``internal``. The organ/evidence slice is a declared secondary
  report, not a separate decision;
* the instance input is the RELEVANT subgraph: nodes on some S->T path (descendants of S intersected with
  ancestors of T). Instances are deduplicated across commits by the digest of (S, T, relevant subgraph); the
  earliest-listed commit (closest to the base) keeps the instance;
* instance id = ``sha256(S|T|subgraph digest)[:16]``; the split is by that id (``split.py``).

Nothing here imports or calls any arm.
"""
from __future__ import annotations

import ast
from collections import deque
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
COMMIT_STRIDE = 12
MAX_COMMITS = 22
SOURCES = ("greg.cli", "greg.missions", "greg.body", "greg.gravity", "greg.remote", "greg.console")
TARGET_ROOTS = ("adapters", "organs", "provenance", "events", "loom", "embassy")
TARGET_MODULES = ("greg.daleobanks_bridge", "greg.foundry_bridge", "greg.journal", "greg.artifacts",
                  "greg.appraisal", "greg.precedents")


def git(*args: str, cwd: Path = ROOT) -> bytes:
    return subprocess.run(("git", *args), cwd=cwd, check=True, capture_output=True).stdout


def resolve(ref: str, cwd: Path = ROOT) -> str:
    return git("rev-parse", "--verify", ref + "^{commit}", cwd=cwd).decode().strip()


def commit_list(base: str, cwd: Path = ROOT) -> list[str]:
    shas = git("rev-list", "--first-parent", base, cwd=cwd).decode().split()
    return shas[::COMMIT_STRIDE][:MAX_COMMITS]


def module_name(path: str) -> str | None:
    if not path.endswith(".py") or path.startswith("tests/") or "/tests/" in path:
        return None
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts or not all(p.isidentifier() for p in parts):
        return None
    return ".".join(parts)


def _files(commit: str, cwd: Path) -> dict[str, str]:
    """module -> blob sha for every tracked module file at ``commit``."""
    out = {}
    for line in git("ls-tree", "-r", commit, cwd=cwd).decode().splitlines():
        meta, path = line.split("\t", 1)
        mode, kind, blob = meta.split()
        name = module_name(path)
        if kind == "blob" and name is not None and mode != "120000":
            out[name] = (blob, path.endswith("__init__.py"))
    return out


def _blobs(blobs: list[str], cwd: Path) -> dict[str, bytes]:
    """Read many blobs with one ``git cat-file --batch``."""
    proc = subprocess.run(("git", "cat-file", "--batch"), cwd=cwd, check=True, capture_output=True,
                          input=("\n".join(blobs) + "\n").encode())
    data, out, i = proc.stdout, {}, 0
    for blob in blobs:
        header_end = data.index(b"\n", i)
        sha, _, size = data[i:header_end].decode().split()
        start = header_end + 1
        out[blob] = data[start:start + int(size)]
        i = start + int(size) + 1
    return out


def _imports(module: str, is_package: bool, source: bytes, modules: set[str]) -> set[str] | None:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    package = module if is_package else module.rpartition(".")[0]
    found = set()

    def deepest(name: str) -> str | None:
        parts = name.split(".")
        for k in range(len(parts), 0, -1):
            cand = ".".join(parts[:k])
            if cand in modules:
                return cand
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hit = deepest(alias.name)
                if hit:
                    found.add(hit)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package.split(".") if package else []
                if node.level - 1 > len(base_parts):
                    continue
                base_parts = base_parts[:len(base_parts) - (node.level - 1)]
                base = ".".join(base_parts + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            if not base:
                continue
            for alias in node.names:
                cand = f"{base}.{alias.name}"
                if cand in modules:
                    found.add(cand)
                else:
                    hit = deepest(base)
                    if hit:
                        found.add(hit)
    found.discard(module)
    return found


def import_graph(commit: str, cwd: Path = ROOT) -> tuple[dict[str, list[str]], int]:
    """(adjacency module -> sorted imported modules, number of unparsable files) at ``commit``."""
    files = _files(commit, cwd)
    blobs = _blobs(sorted({b for b, _ in files.values()}), cwd)
    names = set(files)
    adj, bad = {}, 0
    for name, (blob, is_pkg) in sorted(files.items()):
        deps = _imports(name, is_pkg, blobs[blob], names)
        if deps is None:
            bad += 1
            deps = set()
        adj[name] = sorted(deps)
    return adj, bad


def _reach(adj: dict[str, list[str]], start: str) -> set[str]:
    seen, q = {start}, deque([start])
    while q:
        for v in adj.get(q.popleft(), ()):
            if v not in seen:
                seen.add(v)
                q.append(v)
    return seen


def is_target(module: str) -> bool:
    return module.split(".")[0] in TARGET_ROOTS or module in TARGET_MODULES


def relevant_subgraph(adj: dict[str, list[str]], s: str, t: str) -> list[list[str]]:
    down = _reach(adj, s)
    rev = {}
    for u, vs in adj.items():
        for v in vs:
            rev.setdefault(v, []).append(u)
    up = _reach(rev, t)
    keep = down & up
    return sorted([u, v] for u in keep for v in adj.get(u, ()) if v in keep)


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def extract(base: str, cwd: Path = ROOT) -> dict:
    """All instances under the declared selection rule, deterministic for a given base commit."""
    instances, seen, commits = [], set(), []
    for commit in commit_list(base, cwd):
        adj, bad = import_graph(commit, cwd)
        n_edges = sum(len(v) for v in adj.values())
        commits.append({"commit": commit, "modules": len(adj), "edges": n_edges, "unparsable": bad})
        for s in SOURCES:
            if s not in adj:
                continue
            direct = set(adj[s])
            for t in sorted(_reach(adj, s) - {s} - direct):
                edges = relevant_subgraph(adj, s, t)
                key = digest({"s": s, "t": t, "edges": edges})
                if key in seen:
                    continue
                seen.add(key)
                iid = hashlib.sha256(f"{s}|{t}|{key}".encode()).hexdigest()[:16]
                nodes = sorted({n for e in edges for n in e})
                instances.append({"instance_id": iid, "commit": commit, "source": s, "target": t,
                                  "target_class": "organ_or_evidence" if is_target(t) else "internal",
                                  "edges": edges, "n_nodes": len(nodes), "n_edges": len(edges),
                                  "subgraph_digest": key})
    return {"base": base, "rule": {"stride": COMMIT_STRIDE, "max_commits": MAX_COMMITS, "sources": list(SOURCES),
                                   "target_roots": list(TARGET_ROOTS), "target_modules": list(TARGET_MODULES)},
            "commits": commits, "instances": instances}


if __name__ == "__main__":
    import sys
    base = resolve(sys.argv[1] if len(sys.argv) > 1 else "HEAD")
    data = extract(base)
    print(json.dumps({"commits": data["commits"], "n_instances": len(data["instances"])}, indent=1))
