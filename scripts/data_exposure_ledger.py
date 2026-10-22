"""All-lineage data-exposure ledger for GREG's Mind (coverage build item B02; directive section 31 item 17).

Derives ``docs/evidence/greg-data-exposure-ledger.json`` from committed artifacts only: this line's tree at HEAD
(PR #158's lineage) and PR #179's tree at a pinned commit (``PIN_179``), plus the #155-lineage versions of the eight
colliding frozen paths that docs/collaboration/MIND-LINEAGE-SOURCE-MANIFEST-2026-10-14.json locates. Every artifact
is read with ``git cat-file`` from a commit, never from the working tree, and no entry is typed by hand.

One record per exposure: a set of instances (seeds, series, dated items or suite items) that one committed artifact
put in one role. It names

* the generator: ``module:function`` with the sha256 of that function's source at the exposure commit (the run's
  ``source_commit`` when a results file names one, else the commit that added the artifact), its static PRNG seeding
  expression and the ``*_instance`` functions it delegates to; or a data file / frozen suite by sha256; or a harness
  file by sha256 when the instances are built inline;
* the seeds (inclusive ranges) or series / item identities;
* the role: dev, review-pilot, train, held-out, canary, admission held-out or P8 held-out;
* the artifact and commit that exposed it, and the lineage (#158, #179, or both when the blob is identical);
* whether the outcomes were looked at, and on what basis (a results file or cycle record that binds the freeze's
  digest; a cycle record that carries a held-out outcome; a test that asserts on the instance).

Reported, not decided: overlaps between exposures of the same generator (including through a delegation observed
on development seeds), shared raw PRNG streams across generators, the same data items under different seeds, and
byte-identical items across frozen suites. Generator aliasing (two seeds or two generators producing byte-identical
instances) is sample-checked on development seeds 0-9 only: ``guard_sample`` refuses any seed in ``FORBIDDEN``.

Read-only: it changes no split, routing or rule and creates no authority. Run:

    PYTHONPATH=. python scripts/data_exposure_ledger.py            # write the ledger
    PYTHONPATH=. python scripts/data_exposure_ledger.py --check    # exit 1 unless the committed ledger rebuilds

Query: ``exposed(generator, seeds)`` (generator is ``module:function``, a genome family, or a data path).
"""
from __future__ import annotations

import argparse
import ast
from functools import lru_cache
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "docs" / "evidence" / "greg-data-exposure-ledger.json"
SCHEMA = "greg-data-exposure-ledger/1"
REF_158 = "HEAD"
PIN_179 = {"pr": 179, "branch": "origin/claude/greg-mind-lineage-convergence",
           "commit": "a3106f6a4c3e11762f7b2dc044ecad0a2a0a1dfb"}
MANIFEST = "docs/collaboration/MIND-LINEAGE-SOURCE-MANIFEST-2026-10-14.json"
L158, L179 = "#158", "#179"
# Seeds reserved and unexposed (or exposed only to a recorded run) that this script must never generate.
FORBIDDEN = ((7000, 9199), (5001, 5040), (1000, 1029), (1100, 1129), (1200, 1399))
SAMPLE_SEEDS = tuple(range(10))
HELDOUT_ROLES = ("held-out", "admission held-out", "P8 held-out", "canary")
ROLES = ("dev", "review-pilot", "train", "held-out", "canary", "admission held-out", "P8 held-out")
REVIEW_RANGE = (3000, 3999)              # the repository's review-seed convention (pilots, review tests)
# development ranges a lane declared in committed evidence before using them (seeds outside 0-9 a test may draw)
DECLARED_DEV_RANGES = {(9300, 9339): "docs/evidence/greg-genome-l3-absent-2026-10-21/README.md"}
GENOMES_DIR = "greg/cognition/genomes/"
RESULT_NAME = re.compile(r"(result|cycle-|canary|heldout|summary)[^/]*\.json$")
HEX64 = re.compile(r"[0-9a-f]{64}")


# ---------------------------------------------------------------- git (committed artifacts only)

def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=check)


@lru_cache(maxsize=None)
def resolve(ref: str) -> str | None:
    out = _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    return out.stdout.decode().strip() if out.returncode == 0 else None


_BATCH: list = []


def _cat_file(spec: str) -> bytes | None:
    """One object through a persistent ``git cat-file --batch`` process (a blob, or None when absent)."""
    if not _BATCH or _BATCH[0].poll() is not None:
        _BATCH[:] = [subprocess.Popen(["git", "cat-file", "--batch"], cwd=ROOT, stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE)]
    proc = _BATCH[0]
    proc.stdin.write(spec.encode() + b"\n")
    proc.stdin.flush()
    header = proc.stdout.readline().decode().split()
    if len(header) != 3:
        return None
    data = proc.stdout.read(int(header[2]))
    proc.stdout.read(1)
    return data if header[1] == "blob" else None


@lru_cache(maxsize=None)
def blob(commit: str, path: str) -> bytes | None:
    return _cat_file(f"{commit}:{path}")


@lru_cache(maxsize=None)
def tree(commit: str) -> tuple[str, ...]:
    return tuple(_git("ls-tree", "-r", "--name-only", commit).stdout.decode().splitlines())


@lru_cache(maxsize=None)
def added_in(commit: str) -> dict:
    """path -> the oldest commit reachable from ``commit`` that added it."""
    out = _git("log", "--diff-filter=A", "--format=%x01%H", "--name-only", commit).stdout.decode()
    found, current = {}, None
    for line in out.splitlines():
        if line.startswith("\x01"):
            current = line[1:]
        elif line.strip():
            found[line.strip()] = current            # log is newest first: the last write is the oldest add
    return found


@lru_cache(maxsize=None)
def blame(commit: str, path: str) -> dict:
    """line number -> the commit that last changed that line."""
    out = _git("blame", "--porcelain", commit, "--", path, check=False).stdout.decode(errors="replace")
    lines, current = {}, None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and re.fullmatch(r"[0-9a-f]{40}", parts[0]):
            current = parts[0]
            lines[int(parts[2])] = current
    return lines


@lru_cache(maxsize=None)
def is_ancestor(commit: str, of: str) -> bool:
    return _git("merge-base", "--is-ancestor", commit, of, check=False).returncode == 0


def sha(data: bytes | None) -> str | None:
    return None if data is None else "sha256:" + hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=None)
def blob_sha(commit: str, path: str) -> str | None:
    return sha(blob(commit, path))


def load_json(commit: str, path: str):
    data = blob(commit, path)
    return None if data is None else json.loads(data)


# ---------------------------------------------------------------- seeds

def ranges(seeds) -> list[list[int]]:
    out = []
    for s in sorted(set(int(x) for x in seeds)):
        if out and s == out[-1][1] + 1:
            out[-1][1] = s
        else:
            out.append([s, s])
    return out


def expand(rs) -> set[int]:
    return {s for a, b in rs for s in range(a, b + 1)}


def guard_sample(seeds) -> tuple[int, ...]:
    """The seeds this script may generate instances for: never a reserved or held-out seed."""
    seeds = tuple(int(s) for s in seeds)
    bad = sorted(s for s in seeds if any(a <= s <= b for a, b in FORBIDDEN))
    if bad:
        raise ValueError(f"refusing to generate reserved or held-out seeds {ranges(bad)}")
    return seeds


def _seed_list(value) -> list[int] | None:
    """A declared seed list: a full list, or an inclusive [first, last] pair (two ints more than one apart)."""
    if not (isinstance(value, list) and value and all(isinstance(v, int) and not isinstance(v, bool)
                                                       for v in value)):
        return None
    if len(value) == 2 and value[1] > value[0] + 1:
        return list(range(value[0], value[1] + 1))
    return list(value)


# ---------------------------------------------------------------- static code identity

@lru_cache(maxsize=None)
def module_tree(commit: str, module: str):
    path = module.replace(".", "/") + ".py"
    data = blob(commit, path)
    if data is None:
        return None
    src = data.decode()
    return src, ast.parse(src), path, sha(data)


def _top_function(parsed, name: str):
    for node in parsed.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _prng(fn) -> list[str]:
    params = [a.arg for a in fn.args.args]
    out = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
            if name in ("Random", "default_rng", "RandomState", "seed") and node.args:
                arg = ast.unparse(node.args[0])
                out.add(f"{name}({'<seed>' if params and arg == params[0] else arg})")
    return sorted(out)


def _delegates(fn) -> list[str]:
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and node.id.endswith("_instance") and node.id != fn.name:
            names.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr.endswith("_instance"):
            names.add(ast.unparse(node))
    return sorted(names)


@lru_cache(maxsize=None)
def function_identity(commit: str, module: str, function: str) -> dict:
    """``module:function`` at ``commit``: the sha256 of the function's source, its seeding and its delegates."""
    ident = {"kind": "code", "key": f"{module}:{function}", "module": module, "function": function,
             "commit": commit}
    parsed = module_tree(commit, module)
    fn = None if parsed is None else _top_function(parsed[1], function)
    if fn is None:
        return {**ident, "resolved": False,
                "why": "module absent at commit" if parsed is None else "function absent at commit"}
    source = ast.get_source_segment(parsed[0], fn) or ""
    return {**ident, "resolved": True, "code_sha256": sha(source.encode()), "module_file_sha256": parsed[3],
            "prng": _prng(fn), "delegates": _delegates(fn)}


def _import_aliases(parsed, package: str) -> dict:
    """alias -> dotted target for every import in a module (top level and inside functions)."""
    out = {}
    for node in ast.walk(parsed):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[: len(package.split(".")) - (node.level - 1)]
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            for a in node.names:
                out[a.asname or a.name] = f"{mod}.{a.name}"
        elif isinstance(node, ast.Import):
            for a in node.names:
                out[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
    return out


def _target(expr, aliases: dict, here: str) -> tuple[str, str] | None:
    """(module, function) for an expression naming a generator: ``f``, ``mod.f`` or an imported ``f``."""
    if isinstance(expr, ast.Name):
        dotted = aliases.get(expr.id)
        if dotted:
            mod, _, fn = dotted.rpartition(".")
            return mod, fn
        return here, expr.id
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        mod = aliases.get(expr.value.id)
        return (mod, expr.attr) if mod else None
    return None


@lru_cache(maxsize=None)
def genome_generators(commit: str) -> dict:
    """family -> (module, function) of its ``instance`` generator, read statically from the genome modules."""
    out = {}
    for path in tree(commit):
        if not (path.startswith(GENOMES_DIR) and path.endswith(".py")) or "/" in path[len(GENOMES_DIR):]:
            continue
        module = path[:-3].replace("/", ".")
        parsed = module_tree(commit, module)
        if parsed is None:
            continue
        aliases = _import_aliases(parsed[1], module.rpartition(".")[0])
        for node in ast.walk(parsed[1]):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Executable"):
                continue
            inst = next((k.value for k in node.keywords if k.arg == "instance"), None)
            family = next((k.value.value for sub in ast.walk(node) if isinstance(sub, ast.Call)
                           for k in sub.keywords if k.arg == "family" and isinstance(k.value, ast.Constant)
                           and isinstance(k.value.value, str)), None)
            target = None if inst is None else _target(inst, aliases, module)
            if family and target:
                out[family] = target
    return out


def called_generator(commit: str, module: str, function: str) -> tuple[str, str] | None:
    """The ``*_instance`` generator a split/canary function calls, resolved through its imports."""
    parsed = module_tree(commit, module)
    if parsed is None:
        return None
    fn = _top_function(parsed[1], function) if function else parsed[1]
    if fn is None:
        return None
    aliases = _import_aliases(parsed[1], module.rpartition(".")[0])
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr.endswith("_instance"):
            target = _target(node.func, aliases, module)
            if target:
                return target
    return None


def dict_generators(commit: str, module: str, name: str = "BENCHMARKS") -> dict:
    """family -> function for a module-level ``NAME = {"family": function, ...}`` table."""
    parsed = module_tree(commit, module)
    if parsed is None:
        return {}
    for node in parsed[1].body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets) \
                and isinstance(node.value, ast.Dict):
            return {k.value: v.id for k, v in zip(node.value.keys, node.value.values)
                    if isinstance(k, ast.Constant) and isinstance(v, ast.Name)}
    return {}


def identity_at(commits, module: str, function: str) -> dict:
    """``function_identity`` at the first of ``commits`` where it resolves (a run's source_commit can predate the
    commit that added an uncommitted harness it ran from); the fallback is recorded."""
    commits = [c for i, c in enumerate(commits) if c and c not in commits[:i]]
    for c in commits:
        ident = function_identity(c, module, function)
        if ident["resolved"]:
            return ident if c == commits[0] else {**ident, "run_commit": commits[0], "resolved_at_fallback":
                                                  "absent at the run's source_commit (run from an uncommitted "
                                                  "tree); resolved at the artifact's commit"}
    return function_identity(commits[0], module, function)


def data_identity(commit: str, path: str) -> dict:
    data = blob(commit, path)
    return {"kind": "data", "key": path, "path": path, "commit": commit, "sha256": sha(data),
            "resolved": data is not None}


# ---------------------------------------------------------------- sources

class Source:
    """One lineage's view: a commit to read, and which of its paths are shared byte-for-byte with the other."""

    def __init__(self, lineage: str, commit: str):
        self.lineage, self.commit = lineage, commit

    def paths(self, pattern: str) -> list[str]:
        rx = re.compile(pattern)
        return sorted(p for p in tree(self.commit) if rx.fullmatch(p))

    def added(self, path: str) -> str:
        return added_in(self.commit).get(path) or self.commit


def _results_index(sources) -> dict:
    """sha256 hex -> results-like files (any lineage) whose text cites it, with their source_commit."""
    out: dict[str, list] = {}
    for src in sources:
        for path in tree(src.commit):
            if not (path.startswith(("docs/evidence/", "tests/evidence/", "cortex/evaluation/"))
                    and RESULT_NAME.search(path)):
                continue
            data = blob(src.commit, path)
            text = data.decode(errors="replace")
            commit = None
            try:
                doc = json.loads(text)
                commit = doc.get("source_commit") if isinstance(doc, dict) else None
            except ValueError:
                pass
            for h in set(HEX64.findall(text)):
                out.setdefault(h, []).append({"path": path, "lineage": src.lineage, "source_commit": commit,
                                              "sha256": sha(data)})
    return out


# ---------------------------------------------------------------- exposure records

def _record(*, lineage, program, artifact, commit, role, generator, seeds=None, items=None, family=None,
            looked_at, basis, extra=None) -> dict:
    rec = {"lineages": [lineage] if isinstance(lineage, str) else sorted(lineage), "program": program,
           "artifact": artifact, "exposure_commit": commit, "role": role, "family": family,
           "generator": generator, "looked_at": looked_at, "looked_at_basis": basis}
    if seeds is not None:
        rec["seeds"] = ranges(seeds)
        rec["n"] = len(set(seeds))
    if items is not None:
        rec["items"] = items
        rec.setdefault("n", items.get("n"))
    if extra:
        rec.update(extra)
    rec["id"] = "|".join([rec["lineages"][0], artifact["path"], role, family or "-",
                          (extra or {}).get("part", "-")])
    return rec


def _linked(results: dict, artifact_sha: str | None) -> list[dict]:
    if not artifact_sha:
        return []
    return sorted(results.get(artifact_sha.removeprefix("sha256:"), []), key=lambda r: (r["lineage"], r["path"]))


def _run_commit(links: list[dict], fallback: str) -> str:
    for link in links:
        if link.get("source_commit") and resolve(link["source_commit"]):
            return link["source_commit"]
    return fallback


def _artifact(src: Source, path: str, commit: str | None = None) -> dict:
    commit = commit or src.commit
    return {"path": path, "commit": src.added(path) if commit == src.commit else commit,
            "sha256": blob_sha(commit, path), "read_at": commit}


def admission_genomes(src: Source, results: dict) -> list[dict]:
    """#158's genome admission freezes: dev seeds and held-out seeds per family, generator per family."""
    out = []
    for path in src.paths(r"docs/evidence/greg-genome-admission/[^/]+/freeze\.json"):
        art = _artifact(src, path)
        inputs = load_json(src.commit, path)["inputs"]
        links = _linked(results, art["sha256"])
        gen_commit = _run_commit(links, art["commit"])
        families = {**genome_generators(art["commit"]), **genome_generators(gen_commit)}
        looked = [lk["path"] for lk in links]
        for family in inputs.get("families", []):
            target = families.get(family)
            gen = identity_at([gen_commit, art["commit"]], *target) if target else {
                "kind": "code", "key": f"genome:{family}", "resolved": False, "commit": gen_commit,
                "why": "no Executable(family=...) with an instance generator at the run commit"}
            extra = _forecast_series(family, inputs, gen_commit)
            out.append(_record(lineage=src.lineage, program="admission", artifact=art, commit=gen_commit,
                               role="dev", family=family, generator=gen, seeds=inputs.get("dev_seeds", []),
                               looked_at=True, basis="development seeds are run by builders (admission --dev) "
                                                     "by protocol", extra={"part": "dev"}))
            out.append(_record(lineage=src.lineage, program="admission", artifact=art, commit=gen_commit,
                               role="admission held-out", family=family, generator=gen,
                               seeds=inputs.get("heldout_seeds", []), looked_at=bool(looked),
                               basis=("results bind this freeze's digest: " + ", ".join(looked)) if looked
                               else "no results file binds this freeze's digest",
                               extra={"part": "heldout", **extra}))
    return out


def _forecast_series(family: str, inputs: dict, commit: str) -> dict:
    """The M4 series identities a forecast admission's held-out seeds drew (identity lookups, no instance built)."""
    if family != "forecast_quantile":
        return {}
    from greg.cognition.genomes import forecasting
    data_path = "cortex/evaluation/data/m4_weekly.json.gz"
    at_run, now = blob_sha(commit, data_path), blob_sha(resolve(REF_158), data_path)
    if at_run != now:
        return {"series": None, "series_why": f"{data_path} at the run commit differs from HEAD's"}
    keys = [forecasting.instance_key(s) for s in inputs.get("heldout_seeds", [])]
    return {"series": sorted(set(keys)), "series_repeated_within": len(keys) - len(set(keys)),
            "data": data_identity(commit, data_path)}


def admission_179(src: Source, results: dict) -> list[dict]:
    """#179's operation-family admission freezes (benchmarks inline in its runners)."""
    out = []
    for path in src.paths(r"cortex/evaluation/genome_admission/freeze[^/]*\.json"):
        art = _artifact(src, path)
        doc = load_json(src.commit, path)
        inputs = doc.get("inputs", {})
        links = _linked(results, art["sha256"])
        gen_commit = _run_commit(links, art["commit"])
        linked_docs = [load_json(src.commit, lk["path"]) for lk in links if lk["lineage"] == src.lineage]
        seeds = _seed_list(inputs.get("seeds")) or next(
            (_seed_list(d.get("seeds")) for d in linked_docs if isinstance(d, dict) and d.get("seeds")), None)
        families = inputs.get("families") or next(
            (sorted(d.get("families", {})) for d in linked_docs if isinstance(d, dict) and d.get("families")), [])
        tables = [(m, {**dict_generators(art["commit"], m), **dict_generators(gen_commit, m)})
                  for m in ("cortex.evaluation.genome_admission.run", "cortex.evaluation.genome_admission.run_v2")]
        if "v2" in path:
            tables.reverse()
        looked = [lk["path"] for lk in links]
        rows = [(f, next(((m, t[f]) for m, t in tables if f in t), None)) for f in families]
        if any(isinstance(d, dict) and "crowd_sparse" in d for d in linked_docs):
            rows.append(("crowd_sparse", ("cortex.evaluation.pr155_crowd_sparse.run", "instance")))
        for family, target in rows:
            gen = identity_at([gen_commit, art["commit"]], *target) if target else {
                "kind": "code", "key": f"benchmark:{family}", "resolved": False, "commit": gen_commit}
            out.append(_record(lineage=src.lineage, program="admission (operation families)", artifact=art,
                               commit=gen_commit, role="admission held-out", family=family, generator=gen,
                               seeds=seeds or [], looked_at=bool(looked),
                               basis=("results bind this freeze's digest: " + ", ".join(looked)) if looked
                               else "no results file binds this freeze's digest", extra={"part": "heldout"}))
    return out


P8_TARGETS = {"constraint_release": ("cr_split", "CR_SPLITS"), "immune_detect": ("immune_split", "IMMUNE_SPLITS"),
              "forecast_quantile": ("forecasting_split", None)}


def _p8_generator(commit: str, target: str) -> dict:
    if target == "forecast_quantile":
        return data_identity(commit, "cortex/evaluation/data/m4_weekly.json.gz")
    found = called_generator(commit, "greg.cognition.evolution", P8_TARGETS[target][0])
    return function_identity(commit, *found) if found else {
        "kind": "code", "key": f"p8:{target}", "resolved": False, "commit": commit}


def p8_cycles(src: Source, results: dict) -> list[dict]:
    """Recorded P8 cycles: train and held-out splits from the cycle's freeze, or (before freezes existed) from
    greg/cognition/evolution.py's named splits, checked against the counts the record carries."""
    from greg.cognition import evolution
    out = []
    for path in src.paths(r"docs/evidence/greg-protected-evolution/[^/]+/cycle-[^/]+\.json"):
        art = _artifact(src, path)
        rec = load_json(src.commit, path)
        target, commit = rec.get("target"), rec.get("source_commit") or art["commit"]
        commit = commit if resolve(commit) else art["commit"]
        stem = path.rsplit("/", 1)[1][:-5]
        split_src, train, held, series = None, None, None, None
        freeze_path = (rec.get("freeze") or {}).get("path")
        if freeze_path and blob(src.commit, freeze_path):
            split = load_json(src.commit, freeze_path)["inputs"]["split"]
            train = [int(s[1:]) for s in split["train"]]
            held = [int(s[1:]) for s in split["heldout"]]
            split_src = freeze_path
        elif target == "forecast_quantile":
            key = f"{path.split('/')[-2]}/{stem}"
            cycle = evolution.COMPLETED_FORECAST_CYCLES.get(key)
            if cycle:
                tr, he, _ = evolution.forecasting_split(cycle["seed"], cycle["excluded_seeds"])
                series = (sorted(tr), sorted(he))
                split_src = "greg/cognition/evolution.py COMPLETED_FORECAST_CYCLES (replayed)"
        else:
            name = "cycle-" + stem.rsplit("-", 1)[1]
            table = getattr(evolution, P8_TARGETS[target][1], {})
            if name in table:
                train, held = list(table[name][0]), list(table[name][1])
                split_src = f"greg/cognition/evolution.py {P8_TARGETS[target][1]}[{name!r}]"
        counts = rec.get("split") or {}
        got = (len(series[0]), len(series[1])) if series else (len(train or []), len(held or []))
        check = {"record_counts": [counts.get("train"), counts.get("heldout")], "derived_counts": list(got),
                 "agree": [counts.get("train"), counts.get("heldout")] == list(got), "split_source": split_src}
        gen = _p8_generator(commit, target)
        heldout = rec.get("heldout") or {}
        looked = bool(heldout.get("n"))
        common = dict(lineage=src.lineage, program=f"P8 {target}", artifact=art, commit=commit, generator=gen,
                      family=target)
        why_not = (f"decision {rec.get('decision')} ({rec.get('reason') or 'no held-out outcome recorded'}); the "
                   f"held-out split is spent by its record but its outcomes were never evaluated")
        if series:
            out.append(_record(role="train", items={"n": len(series[0]), "series": series[0]}, looked_at=True,
                               basis=f"cycle record {path} evaluated its train split",
                               extra={"part": "train", "split_check": check}, **common))
            out.append(_record(role="P8 held-out", items={"n": len(series[1]), "series": series[1]},
                               looked_at=looked, basis=(f"held-out outcome in {path} (n={heldout.get('n')})"
                                                        if looked else why_not),
                               extra={"part": "heldout", "split_check": check}, **common))
        else:
            out.append(_record(role="train", seeds=train or [], looked_at=True,
                               basis=f"cycle record {path} evaluated its train split",
                               extra={"part": "train", "split_check": check}, **common))
            out.append(_record(role="P8 held-out", seeds=held or [], looked_at=looked,
                               basis=(f"held-out outcome in {path} (n={heldout.get('n')})" if looked else why_not),
                               extra={"part": "heldout", "split_check": check}, **common))
    return out


def p8_canaries(src: Source) -> list[dict]:
    out = []
    for path in src.paths(r"docs/evidence/greg-protected-evolution/[^/]+/canary/canary\.json"):
        art = _artifact(src, path)
        rec = load_json(src.commit, path)
        commit = rec.get("source_commit") if resolve(rec.get("source_commit") or "") else art["commit"]
        found = called_generator(commit, "scripts.p8_cr6_canary", None) or called_generator(
            commit, "greg.cognition.evolution", "cr_split")
        gen = function_identity(commit, *found) if found else {"kind": "code", "key": "p8:canary",
                                                                "resolved": False, "commit": commit}
        out.append(_record(lineage=src.lineage, program="P8 constraint_release canary", artifact=art, commit=commit,
                           role="canary", family="constraint_release", generator=gen,
                           seeds=_seed_list(rec.get("seeds")) or [], looked_at=True,
                           basis=f"canary outcomes recorded in {path} (n={rec.get('n')})"))
    return out


def _walk_ranges(value, keys=()):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _walk_ranges(v, keys + (str(k),))
    elif isinstance(value, list):
        seeds = _seed_list(value)
        if seeds and len(value) == 2 and keys and keys[-1] != "search" \
                and any("seed" in k or k == "train_sets" for k in keys):
            yield "/".join(k for k in keys if k != "#"), seeds
        elif not seeds:
            for v in value:
                yield from _walk_ranges(v, keys + ("#",))


def p8_pilots(src: Source) -> list[dict]:
    """Review-seed pilots: every [first, last] seed declaration in each pilot directory's JSON files."""
    out, dirs = [], {}
    for path in src.paths(r"docs/evidence/greg-protected-evolution/[^/]+/pilot/[^/]+\.json"):
        dirs.setdefault(path.rsplit("/", 1)[0], []).append(path)
    for directory, files in sorted(dirs.items()):
        target = "immune_detect" if "immune" in directory else "constraint_release"
        declared, union = {}, set()
        for path in files:
            for key, seeds in _walk_ranges(load_json(src.commit, path)):
                declared.setdefault(key, set()).update(seeds)
                union.update(seeds)
        adds = [src.added(p) for p in files]
        commit = max(sorted(set(adds)), key=adds.count)
        art = {"path": directory + "/", "commit": commit, "read_at": src.commit, "files": [
            {"path": p, "sha256": blob_sha(src.commit, p), "commit": src.added(p)} for p in files]}
        out.append(_record(lineage=src.lineage, program=f"P8 {target} pilot", artifact=art, commit=commit,
                           role="review-pilot", family=target, generator=_p8_generator(commit, target),
                           seeds=union, looked_at=True, basis="pilot outcomes are recorded in these files",
                           extra={"declared": {k: ranges(v) for k, v in sorted(declared.items())}}))
    return out


# --- generic freezes and pre-registrations (P6, P4, cortex seed, crossgeo, #155/#179 runs)

PROGRAMS = (("composition_lift", "P6"), ("learned_routing", "P4"), ("seed_genome", "cortex seed genome"),
            ("developmental_sweep", "developmental sweep"), ("pr155_crowd_sparse", "crowd sparse"),
            ("pr155_f7_audit", "P6 F7 audit"), ("pr155_f8", "P6 F8 diagnostic"), ("evolution/", "P8 routing"),
            ("crossgeo", "cortex crossgeo"), ("freeze-v0", "cortex seed"))


def _program(path: str) -> str:
    return next((name for key, name in PROGRAMS if key in path), "evaluation")


def _suite_items(commit: str, path: str) -> dict | None:
    doc = load_json(commit, path)
    items = doc.get("items") if isinstance(doc, dict) else doc if isinstance(doc, list) else None
    if not isinstance(items, list):
        return None
    parts: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        part = item.get("partition") or (doc.get("partition") if isinstance(doc, dict) else None) or "unlabelled"
        entry = parts.setdefault(part, {"ids": [], "seeds": {}, "content": []})
        entry["ids"].append(str(item.get("item_id")))
        if isinstance(item.get("seed"), int):
            entry["seeds"].setdefault(str(item.get("family")), []).append(item["seed"])
        body = {k: v for k, v in item.items() if k not in ("item_id", "partition")}
        entry["content"].append(hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest())
    return parts


def _referenced_files(inputs: dict) -> list[str]:
    out = set()

    def walk(v, keys=()):
        if isinstance(v, dict):
            for k, x in v.items():
                if isinstance(k, str) and "/" in k and (".json" in k or ".py" in k or ".gz" in k):
                    out.add(k)
                walk(x, keys + (k,))
        elif isinstance(v, list):
            for x in v:
                walk(x, keys)
    walk(inputs)
    return sorted(out)


def _suite_paths(commit: str, inputs: dict, path: str) -> list[str]:
    """Suite files a freeze binds: by the digests it records, or by path."""
    digests, named = set(), set()

    def walk(v, keys=()):
        if isinstance(v, dict):
            for k, x in v.items():
                walk(x, keys + (str(k),))
        elif isinstance(v, str) and any("suite" in k for k in keys):
            if re.fullmatch(r"(sha256:)?[0-9a-f]{64}", v):
                digests.add(v.removeprefix("sha256:"))
            elif v.endswith(".json") and "/" in v:
                named.add(v)
    walk(inputs)
    by_path = [p for p in _referenced_files(inputs) if re.search(r"suite[^/]*\.json$", p)] + sorted(named)
    if not digests:
        return sorted(set(by_path))
    folder = path.rsplit("/", 1)[0]
    candidates = [p for p in tree(commit) if re.search(r"(suite[^/]*|suites/[^/]+)\.json$", p)
                  and (p.startswith(folder) or p.startswith("cortex/evaluation/suites/"))]
    found = [p for p in candidates if (blob_sha(commit, p) or "").removeprefix("sha256:") in digests]
    return sorted(set(found) | set(by_path))


SEED_KEY = re.compile(r"(^|_)seeds$")


def _seed_declarations(inputs: dict) -> list[tuple[str, str | None, list[int]]]:
    """(role, family, seeds) for every seed declaration in a freeze's or pre-registration's inputs."""
    out = []
    for key, value in inputs.items():
        if not SEED_KEY.search(key):
            continue
        role = "dev" if key.startswith("dev") else "held-out"
        if isinstance(value, dict):
            for family, parts in value.items():
                if isinstance(parts, list) and parts and all(isinstance(p, list) for p in parts):
                    for i, part in enumerate(parts):
                        seeds = _seed_list(part)
                        if seeds:
                            out.append(("dev" if i < len(parts) - 1 else "held-out", family, seeds))
                else:
                    seeds = _seed_list(parts)
                    if seeds:
                        out.append((role, family, seeds))
        else:
            seeds = _seed_list(value)
            if seeds:
                out.append((role, None, seeds))
    return out


def _partition_declarations(inputs: dict) -> list[tuple[str, dict]]:
    out = []
    part = inputs.get("partition")
    if isinstance(part, list) and len(part) == 2 and all(isinstance(p, list) for p in part):
        out += [("dev", {"names": sorted(part[0])}), ("held-out", {"names": sorted(part[1])})]
    elif isinstance(part, dict):
        for name, span in part.items():
            if name in ("dev", "development"):
                out.append(("dev", {"dates": span}))
            elif "held" in name:
                out.append(("held-out", {"dates": span}))
    return out


def generic_freezes(src: Source, results: dict, collisions: list[tuple[str, str]]) -> tuple[list, list]:
    """Every other freeze / pre-registration JSON under cortex/evaluation (and the #155 collision versions)."""
    out, unparsed = [], []
    paths = [(p, src.commit) for p in src.paths(r"cortex/evaluation/(?!genome_admission/).*(freeze|prereg)[^/]*\.json")]
    paths += collisions
    for path, commit in paths:
        art = _artifact(src, path, commit)
        doc = load_json(commit, path)
        inputs = doc.get("inputs", doc) if isinstance(doc, dict) else {}
        links = _linked(results, art["sha256"])
        looked = [lk["path"] for lk in links]
        run_commit = _run_commit(links, art["commit"])
        suites = _suite_paths(art["commit"], inputs, path)
        data = [p for p in _referenced_files(inputs) if p.startswith("cortex/evaluation/data/") and p.endswith(".gz")]
        harness = [p for p in _referenced_files(inputs) if re.search(r"cortex/evaluation/.*(run|build|suite)[^/]*\.py$", p)
                   and not p.endswith("__init__.py")]
        files = [{"path": p, "sha256": blob_sha(art["commit"], p)} for p in sorted(set(suites + data + harness))]
        gen = {"kind": "suite" if suites else "data" if data else "harness",
               "key": "|".join(f"{f['path']}@{f['sha256']}" for f in files) or f"harness:{path}",
               "files": files, "resolved": bool(files), "commit": run_commit,
               "function": None, "why": "instances built inline by the harness or materialised in a frozen suite"}
        base = dict(lineage=src.lineage, program=_program(path), artifact=art, commit=run_commit, generator=gen)
        held_role = "P8 held-out" if base["program"].startswith("P8") else "held-out"
        basis_seen = ("results bind this freeze's digest: " + ", ".join(looked)) if looked else \
            "no results file binds this freeze's digest"
        found = False
        for role, family, seeds in _seed_declarations(inputs):
            found = True
            role = held_role if role == "held-out" else role
            out.append(_record(role=role, family=family, seeds=seeds,
                               looked_at=True if role == "dev" else bool(looked),
                               basis="development partition" if role == "dev" else basis_seen,
                               extra={"part": f"{role}:{family or '-'}"}, **base))
        for role, items in _partition_declarations(inputs):
            found = True
            role = held_role if role == "held-out" else role
            out.append(_record(role=role, items={"n": len(items.get("names", [])) or None, **items},
                               looked_at=True if role == "dev" else bool(looked),
                               basis="development partition" if role == "dev" else basis_seen,
                               extra={"part": f"partition:{role}"}, **base))
        if not found:
            for spath in suites:
                parts = _suite_items(art["commit"], spath) or {}
                for part, entry in sorted(parts.items()):
                    found = True
                    role = "dev" if part in ("dev", "development", "smoke", "selection") else held_role
                    items = {"n": len(entry["ids"]), "suite": spath, "partition": part,
                             "ids_sha256": sha("\n".join(sorted(entry["ids"])).encode())}
                    seeds = sorted({s for v in entry["seeds"].values() for s in v})
                    out.append(_record(role=role, items=items, seeds=seeds or None,
                                       looked_at=True if role == "dev" else bool(looked),
                                       basis="development partition" if role == "dev" else basis_seen,
                                       extra={"part": f"suite:{spath}:{part}"}, **base))
        relooks = sorted(p for p in _referenced_files(inputs) if p.startswith("docs/evidence/")
                         and re.search(r"results[^/]*\.json$", p))
        if not found and relooks:
            found = True
            out.append(_record(role=held_role, items={"n": None, "relook_of": relooks}, looked_at=bool(looked),
                               basis=basis_seen + "; a re-evaluation of items whose outcomes the cited results "
                                                  "already published", extra={"part": "relook"}, **base))
        if not found:
            unparsed.append({"path": path, "commit": art["commit"], "read_at": art["read_at"],
                             "lineage": src.lineage,
                             "why": "no seed, partition or suite declaration found in its inputs"})
    return out, unparsed


def preregistration_declarations(src: Source) -> list[dict]:
    """Seed ranges written in PREREGISTRATION.md files (cross-checked against the exposure records)."""
    out = []
    for path in src.paths(r"docs/evidence/.*/PREREGISTRATION\.md"):
        text = blob(src.commit, path).decode(errors="replace")
        found = sorted({(int(a), int(b)) for a, b in re.findall(r"(?<![\d.:-])(\d{3,4})\s*(?:-|–|to)\s*(\d{3,4})(?![\d.:])", text)
                        if int(a) < int(b) and int(b) - int(a) < 2000})
        out.append({"path": path, "lineage": src.lineage, "commit": src.added(path), "sha256": blob_sha(src.commit, path),
                    "declared_ranges": [list(r) for r in found]})
    return out


# --- test fixtures

TEST_FILE = r"tests/.*\.py"


def _literal_seeds(node) -> list[int] | None:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range" \
            and all(isinstance(a, ast.Constant) and isinstance(a.value, int) for a in node.args) \
            and 1 <= len(node.args) <= 2:
        args = [a.value for a in node.args]
        return list(range(*args))
    if isinstance(node, (ast.Tuple, ast.List)) and node.elts and all(
            isinstance(e, ast.Constant) and isinstance(e.value, int) and not isinstance(e.value, bool)
            for e in node.elts):
        return [e.value for e in node.elts]
    return None


def _generator_of_call(call, var, aliases, families, bound) -> tuple[str, str, str | None] | None:
    """(module, function, family) when ``call`` builds an instance from ``var`` (or, with ``var`` None, from an
    integer literal): ``x_instance(seed)``, ``<family item>.instance(seed)``, or a helper given a family name."""
    def uses(arg):
        if var:
            return isinstance(arg, ast.Name) and arg.id == var
        return isinstance(arg, ast.Constant) and isinstance(arg.value, int) and not isinstance(arg.value, bool)
    if not any(uses(a) for a in call.args):
        return None
    f = call.func
    if isinstance(f, ast.Attribute) and f.attr == "instance":
        recv, fam = f.value, None
        if isinstance(recv, ast.Call) and recv.args and isinstance(recv.args[0], ast.Constant):
            fam = recv.args[0].value
        elif isinstance(recv, ast.Subscript) and isinstance(recv.slice, ast.Constant):
            fam = recv.slice.value
        elif isinstance(recv, ast.Name) and recv.id in aliases:
            return (aliases[recv.id], "instance", None)     # a module's own ``instance`` function
        elif isinstance(recv, ast.Name):
            fam = bound.get(recv.id)
        if fam in families:
            return (*families[fam], fam)
        return ("?", ast.unparse(recv) + ".instance", None)
    name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
    if name and name.endswith("_instance"):
        target = _target(f, aliases, "?")
        return (*target, None) if target and target[0] != "?" else ("?", ast.unparse(f), None)
    if var:
        fam = next((a.value for a in call.args if isinstance(a, ast.Constant) and a.value in families), None)
        if fam:
            return (*families[fam], fam)
    return None


def _bound_families(parsed, families) -> dict:
    """Module-level names bound to one family's executable: ``X = library.executables()["fam"]`` or ``item("fam")``."""
    out = {}
    for node in parsed.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            v = node.value
            fam = v.slice.value if isinstance(v, ast.Subscript) and isinstance(v.slice, ast.Constant) else \
                v.args[0].value if isinstance(v, ast.Call) and v.args and isinstance(v.args[0], ast.Constant) else None
            if fam in families:
                out[node.targets[0].id] = fam
    return out


def test_fixtures(src: Source, skip_shared: set) -> list[dict]:
    """Literal seeds tests pass to instance generators, directly or through a loop / parametrize."""
    families = genome_generators(src.commit)
    found: dict[tuple, dict] = {}
    for path in src.paths(TEST_FILE):
        if path in skip_shared:
            continue
        text = blob(src.commit, path).decode(errors="replace")
        if "instance" not in text:
            continue
        parsed = ast.parse(text)
        aliases = _import_aliases(parsed, "tests")
        for node in ast.walk(parsed):                 # ``D = developmental``: a local name for an imported module
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                    and isinstance(node.value, ast.Name) and node.value.id in aliases:
                aliases.setdefault(node.targets[0].id, aliases[node.value.id])
        bound = _bound_families(parsed, families)
        scopes = []                                   # (var, seeds, body nodes, line)
        for node in ast.walk(parsed):
            if isinstance(node, ast.For):
                seeds = _literal_seeds(node.iter)
                if seeds and isinstance(node.target, ast.Name):
                    scopes.append((node.target.id, seeds, node.body, node.lineno))
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
                for gen in node.generators:
                    seeds = _literal_seeds(gen.iter)
                    if seeds and isinstance(gen.target, ast.Name):
                        elts = [node.elt] if hasattr(node, "elt") else [node.key, node.value]
                        scopes.append((gen.target.id, seeds, elts, node.lineno))
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Call) and ast.unparse(dec.func).endswith("parametrize") \
                            and len(dec.args) >= 2 and isinstance(dec.args[0], ast.Constant):
                        seeds = _literal_seeds(dec.args[1])
                        if seeds and "," not in dec.args[0].value:
                            scopes.append((dec.args[0].value.strip(), seeds, node.body, dec.lineno))
        for var, seeds, body, line in scopes:
            for stmt in body:
                for call in ast.walk(stmt):
                    if isinstance(call, ast.Call):
                        gen = _generator_of_call(call, var, aliases, families, bound)
                        if gen:
                            key = (path, gen[0], gen[1], line)
                            entry = found.setdefault(key, {"seeds": set(), "line": line, "family": gen[2]})
                            entry["seeds"].update(seeds)
        for call in ast.walk(parsed):
            if isinstance(call, ast.Call) and call.args and isinstance(call.args[0], ast.Constant) \
                    and isinstance(call.args[0].value, int) and not isinstance(call.args[0].value, bool):
                f = call.func
                name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
                if name.endswith("_instance") or name == "instance":
                    gen = _generator_of_call(call, None, aliases, families, bound)
                    if gen:
                        key = (path, gen[0], gen[1], None)
                        entry = found.setdefault(key, {"seeds": set(), "line": call.lineno, "family": gen[2],
                                                       "lines": set()})
                        entry["seeds"].add(call.args[0].value)
                        entry.setdefault("lines", set()).add(call.lineno)
    out = []
    for (path, module, function, _), entry in sorted(found.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2],
                                                                                  kv[0][3] or 0)):
        line_set = sorted(entry.get("lines") or {entry["line"]})
        commits = sorted({lines_c for ln in line_set if (lines_c := blame(src.commit, path).get(ln))})
        commit = commits[-1] if commits else src.added(path)
        local = module == "?" and function in _module_functions(src.commit, path)
        gen = function_identity(commit, module, function) if module != "?" else {
            "kind": "test-local", "key": f"{path}:{function}", "resolved": True, "commit": commit,
            "why": "a helper defined in the test file itself; it is no genome or admission generator"} if local else {
            "kind": "code", "key": function, "resolved": False, "commit": commit,
            "why": "receiver not resolved statically"}
        seeds = sorted(entry["seeds"])
        review = all(REVIEW_RANGE[0] <= s <= REVIEW_RANGE[1] for s in seeds)
        art = {"path": path, "commit": src.added(path), "sha256": blob_sha(src.commit, path), "lines": line_set,
               "line_commits": commits}
        out.append(_record(lineage=src.lineage, program="test fixture", artifact=art, commit=commit,
                           role="review-pilot" if review else "dev", family=entry["family"], generator=gen,
                           seeds=seeds, looked_at=True, basis="a test asserts on these instances",
                           extra={"part": f"{module}:{function}:{line_set[0]}"}))
    return out


def _module_functions(commit, path) -> set:
    """Names of the functions defined at module level in ``path`` at ``commit``."""
    try:
        tree = ast.parse((blob(commit, path) or b"").decode())
    except (SyntaxError, ValueError, UnicodeDecodeError):
        return set()
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


# ---------------------------------------------------------------- aliasing (development seeds only)

def _canon(value):
    try:
        import numpy as np
    except ImportError:                              # pragma: no cover
        np = None
    if isinstance(value, dict):
        return {"__dict__": sorted(([json.dumps(_canon(k), sort_keys=True), _canon(v)] for k, v in value.items()),
                                   key=lambda kv: kv[0])}
    if isinstance(value, (list, tuple)):
        return [_canon(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return {"__set__": sorted(json.dumps(_canon(v), sort_keys=True) for v in value)}
    if isinstance(value, float):
        return {"__float__": repr(value)}
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if np is not None and isinstance(value, np.ndarray):
        return {"__ndarray__": [str(value.dtype), list(value.shape), hashlib.sha256(value.tobytes()).hexdigest()]}
    if np is not None and isinstance(value, np.generic):
        return _canon(value.item())
    if hasattr(value, "nodes") and hasattr(value, "edges"):
        return {"__graph__": [_canon(sorted(map(repr, value.nodes(data=True)))),
                              _canon(sorted(map(repr, value.edges(data=True))))]}
    return {"__repr__": repr(value)}


def instance_digest(fn, seed: int) -> str:
    return hashlib.sha256(json.dumps(_canon(fn(seed)), sort_keys=True).encode()).hexdigest()


def current_generators() -> dict:
    """Every single-argument ``*_instance(seed)`` generator in this tree's genome modules."""
    from greg.cognition.genomes import library
    out = {}
    for name in library.MODULES:
        try:
            module = importlib.import_module(name)
        except ModuleNotFoundError:
            continue
        for attr, fn in sorted(vars(module).items()):
            if (attr.endswith("_instance") or attr == "instance") and inspect.isfunction(fn) \
                    and fn.__module__ == name and list(inspect.signature(fn).parameters) == ["seed"]:
                out[f"{name}:{attr}"] = fn
    return out


def aliasing(seeds=SAMPLE_SEEDS) -> dict:
    seeds = guard_sample(seeds)
    gens = current_generators()
    digests = {key: {s: instance_digest(fn, s) for s in seeds} for key, fn in sorted(gens.items())}
    within = []
    for key, by_seed in digests.items():
        groups: dict[str, list] = {}
        for s, d in by_seed.items():
            groups.setdefault(d, []).append(s)
        for d, ss in sorted(groups.items()):
            if len(ss) > 1:
                within.append({"generator": key, "seeds": sorted(ss)})
    cross, equivalences = [], []
    keys = sorted(digests)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            same_seed = sorted(s for s in seeds if digests[a][s] == digests[b][s])
            other = sorted([sa, sb] for sa in seeds for sb in seeds if sa != sb and digests[a][sa] == digests[b][sb])
            if same_seed or other:
                cross.append({"a": a, "b": b, "same_seed": same_seed, "different_seeds": other})
            if same_seed and not other:
                rule = next(({"modulus": m, "residues": sorted({s % m for s in same_seed})} for m in range(2, 7)
                             if same_seed == [s for s in seeds if s % m in {x % m for x in same_seed}]), None)
                if rule:
                    equivalences.append({"a": a, "b": b, **rule,
                                         "basis": f"byte-identical on development seeds {same_seed}; inferred from "
                                                  f"seeds {list(seeds)} only"})
    return {"sample_seeds": list(seeds), "generators_sampled": len(digests), "within_generator_duplicates": within,
            "cross_generator_identical": cross, "equivalences": equivalences,
            # a digest of which sampled instances are equal, not of their bytes: generator outputs carry platform
            # numerics (CI and local differ), while the equalities the conclusions rest on do not
            "equality_digest": sha(json.dumps(_equality_classes(digests), sort_keys=True).encode())}


def _equality_classes(digests: dict) -> dict:
    """Each (generator, seed) mapped to the index of its equal-instance class, numbered in sorted order."""
    index: dict[str, int] = {}
    out = {}
    for key in sorted(digests):
        for s in sorted(digests[key]):
            out[f"{key}|{s}"] = index.setdefault(digests[key][s], len(index))
    return out


# ---------------------------------------------------------------- overlaps

def _seedset(rec) -> set[int]:
    return expand(rec.get("seeds") or [])


def _gen_key(rec) -> str | None:
    g = rec.get("generator") or {}
    return g.get("key") if g.get("resolved") else None


def overlaps(records: list[dict], alias: dict) -> dict:
    by_key: dict[str, list] = {}
    for rec in records:
        key = _gen_key(rec)
        if key and rec.get("seeds"):
            by_key.setdefault(key, []).append((rec, _seedset(rec), None))
    for eq in alias["equivalences"]:
        for src_key, dst_key in ((eq["a"], eq["b"]), (eq["b"], eq["a"])):
            for rec, seeds, via in list(by_key.get(src_key, [])):
                if via is None:
                    mapped = {s for s in seeds if s % eq["modulus"] in eq["residues"]}
                    if mapped:
                        by_key.setdefault(dst_key, []).append((rec, mapped, f"{src_key} = {dst_key} on seeds "
                                                                          f"= {eq['residues']} mod {eq['modulus']}"))
    same = []
    for key, entries in sorted(by_key.items()):
        for i, (a, sa, va) in enumerate(entries):
            for b, sb, vb in entries[i + 1:]:
                if a["id"] == b["id"] or a["artifact"]["path"] == b["artifact"]["path"]:
                    continue
                if a["role"] == "dev" and b["role"] == "dev":
                    continue
                common = sa & sb
                if not common:
                    continue
                ga, gb = a["generator"], b["generator"]
                same.append({"kind": "same_generator", "generator": key, "a": a["id"], "b": b["id"],
                             "roles": [a["role"], b["role"]], "lineages": sorted(set(a["lineages"] + b["lineages"])),
                             "seeds": ranges(common), "n": len(common),
                             "same_code": ga.get("code_sha256") == gb.get("code_sha256") if ga.get("code_sha256")
                             and gb.get("code_sha256") else None,
                             "via": va or vb,
                             "involves_heldout": a["role"] in HELDOUT_ROLES or b["role"] in HELDOUT_ROLES})
    raw = [r for r in records if r.get("seeds") and "Random(<seed>)" in ((r["generator"] or {}).get("prng") or [])]
    streams: dict[tuple, dict] = {}
    for i, a in enumerate(raw):
        for b in raw[i + 1:]:
            if _gen_key(a) == _gen_key(b) or a["artifact"]["path"] == b["artifact"]["path"] \
                    or not (a["role"] in HELDOUT_ROLES or b["role"] in HELDOUT_ROLES):
                continue
            common = _seedset(a) & _seedset(b)
            if common:
                pair = tuple(sorted([(a["artifact"]["path"], a["role"]), (b["artifact"]["path"], b["role"])]))
                entry = streams.setdefault(pair, {"kind": "shared_raw_prng_stream",
                                                  "a": {"artifact": pair[0][0], "role": pair[0][1]},
                                                  "b": {"artifact": pair[1][0], "role": pair[1][1]},
                                                  "lineages": set(), "generator_pairs": set(), "seeds": set()})
                entry["lineages"].update(a["lineages"] + b["lineages"])
                entry["generator_pairs"].add(tuple(sorted([_gen_key(a), _gen_key(b)])))
                entry["seeds"] |= common
    stream = [{**e, "lineages": sorted(e["lineages"]), "generator_pairs": len(e["generator_pairs"]),
               "n": len(e["seeds"]), "seeds": ranges(e["seeds"])} for _, e in sorted(streams.items())]
    crossing: dict[tuple, dict] = {}
    held = [r for r in records if r.get("seeds") and r["role"] in HELDOUT_ROLES]
    for i, a in enumerate(held):
        for b in held[i + 1:]:
            if {tuple(a["lineages"]), tuple(b["lineages"])} != {(L158,), (L179,)} or _gen_key(a) == _gen_key(b):
                continue
            common = _seedset(a) & _seedset(b)
            if common:
                first, second = (a, b) if a["lineages"] == [L158] else (b, a)
                pair = (first["artifact"]["path"], first["artifact"]["commit"], second["artifact"]["path"],
                        second["artifact"]["commit"])
                entry = crossing.setdefault(pair, {"kind": "seed_number_only_across_lineages",
                                                   L158: {"artifact": pair[0], "commit": pair[1]},
                                                   L179: {"artifact": pair[2], "commit": pair[3]},
                                                   "generator_pairs": set(), "seeds": set()})
                entry["generator_pairs"].add((_gen_key(first), _gen_key(second)))
                entry["seeds"] |= common
    cross = [{**e, "generator_pairs": len(e["generator_pairs"]), "n": len(e["seeds"]), "seeds": ranges(e["seeds"])}
             for _, e in sorted(crossing.items())]
    data = []
    series = [r for r in records if (r.get("items") or {}).get("series") or r.get("series")]
    for i, a in enumerate(series):
        for b in series[i + 1:]:
            sa = set((a.get("items") or {}).get("series") or a.get("series") or [])
            sb = set((b.get("items") or {}).get("series") or b.get("series") or [])
            if sa & sb and a["artifact"]["path"] != b["artifact"]["path"]:
                data.append({"kind": "same_data_items", "a": a["id"], "b": b["id"], "roles": [a["role"], b["role"]],
                             "n": len(sa & sb), "items": sorted(sa & sb)})
    return {"same_generator": same, "shared_raw_prng_stream": stream, "seed_number_only_across_lineages": cross,
            "same_data_items": data}


def suite_identity(suites: list[tuple[str, str, str, str]]) -> list[dict]:
    """Byte-identical items (ignoring id and partition) across different frozen suites or partitions."""
    index: dict[str, list] = {}
    for lineage, commit, path, digest in suites:
        for part, entry in sorted((_suite_items(commit, path) or {}).items()):
            for item_id, h in zip(entry["ids"], entry["content"]):
                index.setdefault(h, []).append((lineage, path, digest, part, item_id))
    pairs: dict[tuple, int] = {}
    for h, owners in index.items():
        owners = sorted(set(owners))
        for i, a in enumerate(owners):
            for b in owners[i + 1:]:
                if (a[2], a[3]) == (b[2], b[3]):
                    continue
                pairs[(a[:4], b[:4])] = pairs.get((a[:4], b[:4]), 0) + 1
    out = []
    for (a, b), n in sorted(pairs.items()):
        if a[3] == b[3] == "dev" or (a[2] == b[2]):
            continue
        out.append({"kind": "identical_suite_items", "a": {"lineage": a[0], "suite": a[1], "sha256": a[2],
                                                           "partition": a[3]},
                    "b": {"lineage": b[0], "suite": b[1], "sha256": b[2], "partition": b[3]}, "n": n,
                    "involves_heldout": "held" in a[3] or "held" in b[3]})
    return out


# ---------------------------------------------------------------- build

def _collisions(src158: Source) -> list[tuple[str, str]]:
    manifest = load_json(src158.commit, MANIFEST) or {}
    out = []
    for c in manifest.get("frozen_path_collisions", []):
        p155 = (c.get("lineages") or {}).get("pr155") or {}
        commit = p155.get("last_changed_in")
        if re.search(r"(freeze|prereg)[^/]*\.json$", c["path"]) and commit and resolve(commit):
            out.append((c["path"], commit))
    return sorted(out)


CONVERGED_MAP = "docs/collaboration/MIND-LINEAGE-RECONCILIATION-MAP-2026-10-14.json"


def _trees() -> tuple[str | None, str | None]:
    """(#158 tree, #179 tree). On #158's line: HEAD and PIN_179. On #179's converged tree, which merges #158, HEAD is
    #179's own tree and #158's is the commit the reconciliation map pins, an ancestor of HEAD; otherwise every
    #179 artifact would read as #158's and #179's newer runs would be missed (merge of #158 fa0d92a0 into #179)."""
    head = REF_158 if resolve(REF_158) else None          # symbolic, so a rebuild after a commit is identical
    pinned = (load_json(head, CONVERGED_MAP) or {}).get("pr158") if head else None
    if pinned and resolve(pinned) and resolve(pinned) != resolve(head) and is_ancestor(pinned, head) \
            and resolve(PIN_179["commit"]) and is_ancestor(PIN_179["commit"], head):
        return pinned, head
    return head, resolve(PIN_179["commit"])


def build() -> dict:
    head, pin = _trees()
    if pin is None:
        raise RuntimeError(f"PR #179's pinned commit {PIN_179['commit']} is not in this clone; fetch "
                           f"{PIN_179['branch']}")
    s158, s179 = Source(L158, head), Source(L179, pin)
    results = _results_index([s158, s179])

    def shared(path):
        return blob(head, path) is not None and blob(head, path) == blob(pin, path)

    records, unparsed = [], []
    records += admission_genomes(s158, results) + p8_cycles(s158, results) + p8_canaries(s158) + p8_pilots(s158)
    g158, u158 = generic_freezes(s158, results, [])
    records += g158
    unparsed += u158
    records += test_fixtures(s158, set())
    # #179: only what is not byte-identical at the same path on this line, plus #155's colliding freezes
    shared_paths = {p for p in tree(pin) if shared(p)}

    def only_179(rec):
        paths = [f["path"] for f in rec["artifact"].get("files", [])] or [rec["artifact"]["path"]]
        return rec["artifact"].get("read_at", pin) != pin or not all(p in shared_paths for p in paths)

    r179 = admission_179(s179, results)
    r179 += admission_genomes(s179, results) + p8_cycles(s179, results) + p8_canaries(s179) + p8_pilots(s179)
    g179, u179 = generic_freezes(s179, results, _collisions(s158))
    r179 = [r for r in r179 + g179 if only_179(r)]
    unparsed += [u for u in u179 if u["path"] not in shared_paths or u["read_at"] != pin]
    r179 += test_fixtures(s179, shared_paths)
    records += r179
    base = (load_json(head, MANIFEST) or {}).get("common_base")
    for rec in records:
        # origin: the lineage whose history added the artifact (both when it predates the two lineages' split);
        # present_in: the trees that hold it byte-identically today (#179 merged parts of this line)
        commit = rec["artifact"]["commit"]
        if base and resolve(base) and is_ancestor(commit, base):
            rec["lineages"] = [L158, L179]
        elif is_ancestor(commit, head):
            rec["lineages"] = [L158]
        else:
            rec["lineages"] = [L179]
        paths = [f["path"] for f in rec["artifact"].get("files", [])] or [rec["artifact"]["path"]]
        read = rec["artifact"].get("read_at", head)
        rec["present_in"] = [lin for lin, ref in ((L158, head), (L179, pin))
                             if all(blob(ref, p) is not None and blob(ref, p) == blob(read, p) for p in paths)]
    by_id: dict[str, dict] = {}
    for rec in records:
        if rec["id"] in by_id:
            rec["id"] += f"|{len([k for k in by_id if k.startswith(rec['id'])])}"
        by_id[rec["id"]] = rec
    records = sorted(by_id.values(), key=lambda r: r["id"])
    alias = aliasing()
    over = overlaps(records, alias)
    suites = sorted({(r["lineages"][0], r["artifact"]["commit"], f["path"], f["sha256"])
                     for r in records if (r.get("generator") or {}).get("kind") == "suite"
                     for f in r["generator"]["files"] if re.search(r"(suite[^/]*|suites/[^/]+)\.json$", f["path"])})
    unique: dict[tuple, tuple] = {}
    for entry in suites:                     # one reading per (path, digest), whichever lineage cites it
        unique.setdefault((entry[2], entry[3]), entry)
    over["identical_suite_items"] = suite_identity([s for s in unique.values() if blob(s[1], s[2])])
    prereg = preregistration_declarations(s158) + [
        d for d in preregistration_declarations(s179) if d["path"] not in shared_paths]
    covered = {L158: set(), L179: set()}
    for rec in records:
        for lin in rec["lineages"]:
            covered[lin] |= _seedset(rec)
    for d in prereg:
        d["not_in_any_exposure"] = [r for r in d["declared_ranges"]
                                    if not set(range(r[0], r[1] + 1)) <= covered[d["lineage"]]]
    globs = {
        "admission freezes (#158 form)": r"docs/evidence/greg-genome-admission/[^/]+/freeze\.json",
        "admission freezes (#179 operation form)": r"cortex/evaluation/genome_admission/freeze[^/]*\.json",
        "P8 cycle records": r"docs/evidence/greg-protected-evolution/[^/]+/cycle-[^/]+\.json",
        "P8 canaries": r"docs/evidence/greg-protected-evolution/[^/]+/canary/canary\.json",
        "P8 pilot files": r"docs/evidence/greg-protected-evolution/[^/]+/pilot/[^/]+\.json",
        "other freezes and pre-registrations": r"cortex/evaluation/(?!genome_admission/).*(freeze|prereg)[^/]*\.json",
        "PREREGISTRATION.md": r"docs/evidence/.*/PREREGISTRATION\.md",
    }
    coverage = {}
    cited = {f["path"] for r in records for f in r["artifact"].get("files", [])} | {
        r["artifact"]["path"] for r in records} | {d["path"] for d in prereg}
    skipped = {u["path"] for u in unparsed}
    for name, pattern in globs.items():
        for src in (s158, s179):
            matched = src.paths(pattern)
            if src is s179:
                matched = [m for m in matched if m not in shared_paths]
            coverage.setdefault(name, {})[src.lineage] = {
                "glob": pattern, "matched": len(matched),
                "parsed": sum(p in cited for p in matched),
                "no_declaration": sorted(p for p in matched if p in skipped and p not in cited),
                "missing": sorted(p for p in matched if p not in cited and p not in skipped)}
    counts = {"by_role": {}, "by_lineage": {}, "by_role_and_lineage": {}}
    for rec in records:
        lin = "both" if len(rec["lineages"]) == 2 else rec["lineages"][0]
        counts["by_role"][rec["role"]] = counts["by_role"].get(rec["role"], 0) + 1
        counts["by_lineage"][lin] = counts["by_lineage"].get(lin, 0) + 1
        key = f"{rec['role']} / {lin}"
        counts["by_role_and_lineage"][key] = counts["by_role_and_lineage"].get(key, 0) + 1
    counts = {k: dict(sorted(v.items())) for k, v in counts.items()}
    counts["overlaps"] = {k: len(v) for k, v in over.items()}
    counts["overlaps_involving_heldout"] = sum(1 for o in over["same_generator"] if o["involves_heldout"])
    counts["exposures"] = len(records)
    from greg.cognition import evolution
    from greg.cognition.genomes import admission
    reservations = {
        "never_generated_by_this_script": [list(r) for r in FORBIDDEN],
        "p8_reserved": [admission.P8_RESERVED.start, admission.P8_RESERVED.stop - 1],
        "registered_p8_splits": [
            {"target": target, "split": name, "train": ranges(parts[0]), "heldout": ranges(parts[1]),
             "recorded_cycle": any(r["program"] == f"P8 {target}" and r["role"] == "train"
                                   and set(expand(r.get("seeds") or [])) == set(parts[0]) for r in records)}
            for target, table in (("immune_detect", evolution.IMMUNE_SPLITS), ("constraint_release", evolution.CR_SPLITS))
            for name, parts in sorted(table.items())],
    }
    return {
        "schema": SCHEMA,
        "generated_by": "scripts/data_exposure_ledger.py",
        "rule": ("one record per exposure; generator identity is module:function plus the sha256 of the function's "
                 "source at the exposure commit (the run's source_commit when a results file names one), a data "
                 "file's or frozen suite's sha256, or a harness file's sha256; looked_at is true only with a "
                 "results file or record that binds the artifact's digest or carries its outcome"),
        "lineage_rule": ("lineages = the origin: the lineage whose history added the artifact, both when it was "
                         "added before the common base in " + MANIFEST + "; present_in = the trees holding it "
                         "byte-identically today"),
        "sources": {L158: {"ref": "HEAD of this line (read with git cat-file; the working tree is not read)"},
                    L179: {**PIN_179, "shared_paths_counted_once": True},
                    "#155 collisions": {"manifest": MANIFEST, "read": [list(c) for c in _collisions(s158)]}},
        "roles": list(ROLES),
        "counts": counts,
        "coverage": coverage,
        "unparsed": sorted(unparsed, key=lambda u: (u["lineage"], u["path"], u["commit"])),
        "preregistration_declarations": sorted(prereg, key=lambda d: (d["lineage"], d["path"])),
        "reservations": reservations,
        "aliasing": alias,
        "overlaps": over,
        "exposures": records,
    }


def render(ledger: dict) -> str:
    return json.dumps(ledger, indent=1, sort_keys=True) + "\n"


def load(path: Path = LEDGER) -> dict:
    return json.loads(Path(path).read_text())


def exposed(generator: str, seeds, ledger: dict | None = None) -> list[dict]:
    """Exposures of ``generator`` (``module:function``, a genome family, or a data path) that touch ``seeds``,
    including through a delegation the aliasing sample observed. Returns id, role, lineages, looked_at and the
    overlapping seeds, most consequential (held-out) first."""
    ledger = ledger or load()
    wanted = set(int(s) for s in seeds)
    keys = {generator}
    for rec in ledger["exposures"]:
        if rec.get("family") == generator and (rec.get("generator") or {}).get("key"):
            keys.add(rec["generator"]["key"])
    mapped = {k: wanted for k in keys}
    for eq in ledger["aliasing"]["equivalences"]:
        for a, b in ((eq["a"], eq["b"]), (eq["b"], eq["a"])):
            if a in keys:
                mapped.setdefault(b, set()).update(s for s in wanted if s % eq["modulus"] in eq["residues"])
    out = []
    for rec in ledger["exposures"]:
        key = (rec.get("generator") or {}).get("key")
        hit = mapped.get(key, set()) & expand(rec.get("seeds") or [])
        if hit:
            out.append({"id": rec["id"], "role": rec["role"], "lineages": rec["lineages"],
                        "looked_at": rec["looked_at"], "generator": key, "seeds": ranges(hit)})
    return sorted(out, key=lambda r: (r["role"] not in HELDOUT_ROLES, r["id"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the committed ledger rebuilds byte-identically")
    ap.add_argument("--out", type=Path, default=LEDGER)
    args = ap.parse_args(argv)
    text = render(build())
    if args.check:
        same = args.out.exists() and args.out.read_text() == text
        print("ledger rebuilds byte-identically" if same else f"{args.out} is stale: rebuild it")
        return 0 if same else 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(f"wrote {args.out} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
