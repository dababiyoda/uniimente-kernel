#!/usr/bin/env python3
"""Repository review: one read-only instrument for the recurring structural review.

Usage:
    python scripts/repo_review.py                    # offline report (markdown)
    python scripts/repo_review.py --json             # same, machine-readable
    python scripts/repo_review.py --check            # exit 1 on any hard finding
    python scripts/repo_review.py --github OWNER/REPO --json   # add PR-flow metrics

What it measures, and why each item exists, is in docs/REVIEW_CADENCE.md.
The structural checks here are the same functions the unit tests call
(tests/unit/test_repository_map.py, tests/unit/test_import_layering.py), so a
weekly report and a pull request can never disagree about the rules.

Authority: none. The script reads files and, with --github, the public REST API
(optionally with a read-only token). It writes nothing, posts nothing and
changes no setting. Its output is evidence for a human or agent review; it
decides nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import ast
import json
import os
import re
import statistics
import subprocess
import sys
import urllib.request
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The published boundary distribution (pyproject.toml [tool.setuptools]
# packages). Consumers (WealthMachineIntelligence, DALEOBANKS) install only these,
# so any import from them to another repository package is a latent ImportError
# in a consumer install.
BOUNDARY = ("adapters", "contracts", "events", "provenance")

# Shrink-only ratchets. A new entry fails the check; an entry that no longer
# occurs also fails, so the list can only get shorter. Each kept entry carries
# the reason it is tolerated today. Measured at #196 head 3a2ba265 (2026-11-05).
KEPT_TWO_WAY = {
    ("business", "closure"): "closure registries import the business loop to close it",
    ("capabilities", "cortex"): "router and cortex reference each other's genomes",
    ("capabilities", "greg"): "greg registers capabilities; the router reads greg genomes",
    ("capabilities", "provenance"): "capabilities/router.py uses provenance.digests (the right direction, #254); the "
                                    "cycle is only the deprecated wrapper provenance/witness.py capability_genome() "
                                    "(KEPT_BOUNDARY, pain point S-2), and goes when the wrapper is removed",
    ("closure", "egregore"): "closure probes egregore; egregore reports closure",
    ("closure", "evolution"): "closure probes evolution; evolution uses closure fixtures",
    ("closure", "foundry"): "closure probes foundry; foundry uses closure fixtures",
    ("cortex", "greg"): "greg.cognition bridges cortex, which calls back into greg",
    ("foundry", "greg"): "greg runs foundry systems; foundry systems call greg services",
    ("foundry", "omnimorph"): "omnimorph composes foundry architectures and vice versa",
}
KEPT_BOUNDARY = {
    ("provenance", "capabilities"):
        "only the deprecated wrapper provenance/witness.py capability_genome() imports "
        "capabilities.specs; the genome itself is plain data (GENOME_SPEC) and a "
        "boundary-only install gets a clear ImportError (test_boundary_distribution_works_"
        "installed_alone). Removing the wrapper needs a boundary version bump: owner decision (S-2)",
}

# Entry surfaces that must defer to the canonical reading order in AGENTS.md.
ENTRY_SURFACES = ("CLAUDE.md", "CONTRIBUTING.md", "README.md", ".github/copilot-instructions.md")
CANONICAL_ORDER_MARKER = "<!-- canonical-reading-order -->"


# --------------------------------------------------------------------------- files

def tracked_files(root: Path = ROOT) -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True,
                             text=True, check=True, timeout=60).stdout
        return out.splitlines()
    except (OSError, subprocess.SubprocessError):
        return [str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()
                and ".git" not in p.parts]


def top_level_dirs(root: Path = ROOT) -> list[str]:
    dirs = {p.split("/", 1)[0] for p in tracked_files(root) if "/" in p}
    return sorted(d for d in dirs if not d.startswith("."))


def packages(root: Path = ROOT) -> list[str]:
    return sorted(d for d in top_level_dirs(root) if (root / d / "__init__.py").is_file())


# ------------------------------------------------------------------- orientation

def readme_layout_names(root: Path = ROOT) -> set[str]:
    text = (root / "README.md").read_text(encoding="utf-8")
    start = text.index("## Layout")
    end = text.find("\n## ", start + 1)
    return set(re.findall(r"`/([A-Za-z0-9_.-]+)`", text[start:end if end > 0 else None]))


def dirs_without_readme(root: Path = ROOT) -> list[str]:
    return [d for d in top_level_dirs(root) if not (root / d / "README.md").is_file()]


def dirs_missing_from_layout(root: Path = ROOT) -> list[str]:
    listed = readme_layout_names(root)
    return [d for d in top_level_dirs(root) if d not in listed]


def layout_ghosts(root: Path = ROOT) -> list[str]:
    return sorted(d for d in readme_layout_names(root) if not (root / d).is_dir())


def docs_missing_from_index(root: Path = ROOT) -> list[str]:
    index_path = root / "docs" / "README.md"
    if not index_path.is_file():
        return ["docs/README.md (index missing)"]
    index = index_path.read_text(encoding="utf-8")
    names = sorted(p.name for p in (root / "docs").iterdir()
                   if p.is_file() and p.name != "README.md")
    return [n for n in names if n not in index]


def entry_surfaces_not_deferring(root: Path = ROOT) -> list[str]:
    """Entry files that do not point readers at AGENTS.md's canonical order."""
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    bad = [] if CANONICAL_ORDER_MARKER in agents else ["AGENTS.md (marker missing)"]
    for rel in ENTRY_SURFACES:
        text = (root / rel).read_text(encoding="utf-8")
        if "AGENTS.md#canonical-reading-order" not in text:
            bad.append(rel)
    return bad


def pr_template_ambiguity(root: Path = ROOT) -> list[str]:
    """Two case-variant PR templates must say which one is canonical."""
    upper = root / ".github" / "PULL_REQUEST_TEMPLATE.md"
    lower = root / ".github" / "pull_request_template.md"
    if not (upper.is_file() and lower.is_file()):
        return []
    head = upper.read_text(encoding="utf-8")[:600]
    return [] if "pull_request_template.md" in head else [".github/PULL_REQUEST_TEMPLATE.md"]


# ----------------------------------------------------------------------- layering

def import_edges(root: Path = ROOT) -> dict[tuple[str, str], list[str]]:
    """(importer package, imported package) -> files, module-level and lazy alike."""
    pkgs = set(packages(root))
    edges: dict[tuple[str, str], list[str]] = {}
    for rel in tracked_files(root):
        if not rel.endswith(".py"):
            continue
        top = rel.split("/", 1)[0]
        if top not in pkgs:
            continue
        try:
            tree = ast.parse((root / rel).read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module]
            else:
                continue
            for name in names:
                target = name.split(".", 1)[0]
                if target in pkgs and target != top:
                    edges.setdefault((top, target), [])
                    if rel not in edges[(top, target)]:
                        edges[(top, target)].append(rel)
    return edges


def two_way_pairs(edges) -> set[tuple[str, str]]:
    return {tuple(sorted(e)) for e in edges if (e[1], e[0]) in edges}


def boundary_violations(edges) -> set[tuple[str, str]]:
    return {e for e in edges if e[0] in BOUNDARY and e[1] not in BOUNDARY}


def ratchet(observed: set, kept: dict) -> dict:
    return {"new": sorted(observed - set(kept)), "gone": sorted(set(kept) - observed)}


# ------------------------------------------------------------------ gate liveness

# Mutation-gate scripts that no workflow runs, with the reason each is tolerated.
# A new unwired gate fails, and so does a listed gate once it is wired. ratchet() compares this list with the tree,
# not with what it was, so a gate added here in the same change would pass it: the list's contents are pinned in
# tests/unit/test_repo_health_gates.py (PINNED_UNWIRED), and growing it takes an edit there too.
KEPT_UNWIRED_GATES = {
    "check_seed_mutants.py":
        "run by no workflow, and not green where its solvers are installed. Executed at 8d205324 (2026-11-11): "
        "6/7 caught, exit 1, with requirements-dev and requirements-cognition (z3-solver 5.1.0.0, ortools "
        "9.15.6755): the constraint mutant's named test still passes. With requirements-dev alone it prints 7/7 "
        "and exits 0, but two named tests (constraint, unknown) fail unmutated on a missing solver and the gate "
        "runs no baseline: only 5 of the 7 are shown caught. This entry said '7/7 caught locally with requirements "
        "installed' until then. Wiring it into CI is a founder/CI-owner decision (register S-3); unrepaired, expect "
        "it red there",
}
_PATHLIKE = re.compile(r"^[\w./-]+\.(py|json|md|ya?ml|txt)(::\S+)?$")


# Mutation operations whose text is added rather than found: what follows the path is not an anchor.
NEW_TEXT_OPS = ("append", "create")


def _gate_anchors(gate: Path, root: Path) -> list[tuple[str, str]]:
    """(target file, anchor text) pairs written as literals in a mutation gate.

    Conservative: only a literal tuple/list in which a string naming an existing
    repository .py file is directly followed by a non-path string is read as an
    anchor. Anything else is not inspected, so this never reports a false stale; text an ``append`` or ``create``
    operation adds (NEW_TEXT_OPS) is not an anchor.
    """
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            tree = ast.parse(gate.read_text(encoding="utf-8"))
        except SyntaxError:
            return []
    pairs = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Tuple, ast.List)):
            continue
        vals = [e.value if isinstance(e, ast.Constant) and isinstance(e.value, str) else None
                for e in node.elts]
        for i, target in enumerate(vals[:-1]):
            anchor = vals[i + 1]
            if i and vals[i - 1] in NEW_TEXT_OPS:              # ("append"|"create", path, text): new text, no anchor
                break
            if (target and target.endswith(".py") and (root / target).is_file()
                    and anchor and not _PATHLIKE.match(anchor)):
                pairs.append((target, anchor))
                break
    return pairs


def gate_liveness(root: Path = ROOT) -> dict:
    """Static health of every scripts/ci/check_*mutant*.py gate.

    stale: an anchor that no longer occurs in its target, the failure CI reports
    as STALE only after a long run; multi_site: an anchor that occurs more than
    once (the gate mutates every site; advisory); unwired: no workflow names it.
    """
    workflows = " ".join(p.read_text(encoding="utf-8")
                         for p in sorted((root / ".github" / "workflows").glob("*.y*ml")))
    gates = {}
    for gate in sorted((root / "scripts" / "ci").glob("check_*mutant*.py")):
        anchors = _gate_anchors(gate, root)
        counts = [(t, a, (root / t).read_text(encoding="utf-8").count(a)) for t, a in anchors]
        gates[gate.name] = {
            "anchors_checked": len(counts),
            "stale": [{"target": t, "anchor": a[:80]} for t, a, c in counts if c == 0],
            "multi_site": [{"target": t, "anchor": a[:80], "sites": c} for t, a, c in counts if c > 1],
            "wired": gate.name in workflows,
        }
    return gates


def lint_trend(root: Path = ROOT) -> dict:
    """Count of pyflakes/syntax findings, if ruff is installed. A trend, never a gate."""
    import shutil
    if not shutil.which("ruff"):
        return {"not_run": "ruff not installed"}
    try:
        out = subprocess.run(["ruff", "check", "--select", "F,E9", "--exit-zero",
                              "--output-format", "json", "--no-cache", "."],
                             cwd=root, capture_output=True, text=True, timeout=300)
        findings = json.loads(out.stdout or "[]")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        return {"not_run": f"{type(exc).__name__}: {exc}"}
    by_rule: dict[str, int] = {}
    for f in findings:
        by_rule[f.get("code") or "?"] = by_rule.get(f.get("code") or "?", 0) + 1
    return {"findings": len(findings), "by_rule": dict(sorted(by_rule.items()))}


# ------------------------------------------------------------------------ GitHub

def _get(url: str, token: str | None):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "uniimente-repo-review"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (fixed host)
        return json.load(resp)


def github_metrics(repo: str, token: str | None, limit: int = 100) -> dict:
    """SOP-06 proxies from public PR metadata. Proxies, not the SOP's measures:
    a receipt block is a declaration, not a verified handoff."""
    base = f"https://api.github.com/repos/{repo}"
    open_prs = _get(f"{base}/pulls?state=open&per_page=100", token)
    closed = _get(f"{base}/pulls?state=closed&per_page={min(limit, 100)}", token)
    marker = "<!-- uniimente:receipt -->"
    merged = [p for p in closed if p.get("merged_at")]
    unmerged = [p for p in closed if not p.get("merged_at")]
    words = re.compile(r"\b(stale|supersed|duplicate|rework|re-record|conflict)", re.I)
    return {
        "proxy_note": "metadata proxies for SOP-06; not proof of reading or handoff",
        "open_prs": len(open_prs),
        "open_drafts": sum(1 for p in open_prs if p.get("draft")),
        "recent_closed": len(closed),
        "recent_merged": len(merged),
        "recent_closed_unmerged": len(unmerged),
        "receipt_coverage_recent_closed": round(
            sum(1 for p in closed if marker in (p.get("body") or "")) / len(closed), 3)
        if closed else None,
        "recent_closed_mentioning_rework_words": sum(
            1 for p in closed if words.search(p.get("body") or "")),
        "open_pr_base_branches": dict(sorted(
            {b: sum(1 for p in open_prs if p["base"]["ref"] == b)
             for b in {p["base"]["ref"] for p in open_prs}}.items())),
    }


# ------------------------------------------------------------------------ report

def size_profile(root: Path = ROOT, top: int = 10) -> dict:
    sizes = []
    for rel in tracked_files(root):
        if rel.endswith(".py") and not rel.startswith("tests/"):
            try:
                n = sum(1 for _ in (root / rel).open(encoding="utf-8", errors="replace"))
            except FileNotFoundError:
                continue
            sizes.append((n, rel))
    sizes.sort(reverse=True)
    lines = [n for n, _ in sizes]
    return {"python_files": len(sizes), "python_lines": sum(lines),
            "median_file_lines": statistics.median(lines) if lines else 0,
            "files_over_1500_lines": sum(1 for n in lines if n > 1500),
            "largest": [{"path": p, "lines": n} for n, p in sizes[:top]]}


class _Shape(ast.NodeTransformer):
    """Erase names and literal values so renamed copies of one body compare equal."""

    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)

    def visit_arg(self, node):
        node.arg, node.annotation = "_", None
        return node

    def visit_Constant(self, node):
        return ast.copy_location(ast.Constant(value=type(node.value).__name__), node)


def duplicate_functions(root: Path = ROOT, min_lines: int = 10) -> list[list[dict]]:
    """Function bodies of at least ``min_lines`` repeated in more than one file.

    Copies that differ only in names or literal values count as one shape. A trend
    for the weekly review, never a gate: some copies are deliberate (a frozen
    script, an organ that must not import another).
    """
    groups: dict[str, list[dict]] = {}
    for rel in tracked_files(root):
        if not rel.endswith(".py") or rel.startswith(("tests/", "docs/")) or "/evaluation/" in rel:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tree = ast.parse((root / rel).read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, FileNotFoundError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            length = node.end_lineno - node.lineno
            if length < min_lines:
                continue
            body = [b for b in node.body
                    if not (isinstance(b, ast.Expr) and isinstance(getattr(b, "value", None), ast.Constant))]
            shape = ast.dump(_Shape().visit(ast.Module(body=body, type_ignores=[])), annotate_fields=False)
            key = hashlib.sha256(shape.encode()).hexdigest()
            groups.setdefault(key, []).append({"path": rel, "function": node.name, "lines": length})
    dups = [g for g in groups.values() if len({x["path"] for x in g}) > 1]
    return sorted(dups, key=lambda g: -(len(g) - 1) * g[0]["lines"])


def build_report(root: Path = ROOT, github: str | None = None,
                 kept_two_way: dict | None = None, kept_boundary: dict | None = None,
                 kept_unwired: dict | None = None, lint: bool = False) -> dict:
    kept_two_way = KEPT_TWO_WAY if kept_two_way is None else kept_two_way
    kept_boundary = KEPT_BOUNDARY if kept_boundary is None else kept_boundary
    edges = import_edges(root)
    pairs, boundary = two_way_pairs(edges), boundary_violations(edges)
    hard = {
        "dirs_without_readme": dirs_without_readme(root),
        "dirs_missing_from_readme_layout": dirs_missing_from_layout(root),
        "readme_layout_ghosts": layout_ghosts(root),
        "docs_missing_from_index": docs_missing_from_index(root),
        "entry_surfaces_not_deferring_to_agents": entry_surfaces_not_deferring(root),
        "pr_template_ambiguity": pr_template_ambiguity(root),
        "two_way_package_imports": ratchet(pairs, kept_two_way),
        "boundary_package_imports": ratchet(boundary, kept_boundary),
    }
    gates = gate_liveness(root)
    hard["stale_mutation_anchors"] = sorted(
        f"{g}: {s['target']}" for g, row in gates.items() for s in row["stale"])
    hard["unwired_mutation_gates"] = ratchet(
        {g for g, row in gates.items() if not row["wired"]},
        KEPT_UNWIRED_GATES if kept_unwired is None else kept_unwired)
    report = {
        "schema": "uniimente.repo_review/1",
        "authority": "none; evidence for a review, not a decision",
        "hard_findings": hard,
        "hard_finding_count": sum(
            (len(v["new"]) + len(v["gone"])) if isinstance(v, dict) else len(v)
            for v in hard.values()),
        "layering": {"packages": len(packages(root)), "edges": len(edges),
                     "two_way_pairs_kept": len(kept_two_way),
                     "boundary_violations_kept": len(kept_boundary)},
        "size": size_profile(root),
        "duplicates": duplicate_functions(root),
        "gates": {
            "scripts": len(gates),
            "anchors_checked": sum(r["anchors_checked"] for r in gates.values()),
            "not_statically_checkable": sorted(g for g, r in gates.items() if not r["anchors_checked"]),
            "multi_site_advisory": {g: r["multi_site"] for g, r in gates.items() if r["multi_site"]},
        },
    }
    if lint:
        report["lint"] = lint_trend(root)
    if github:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        try:
            report["github"] = github_metrics(github, token)
        except Exception as exc:  # network is optional; say so instead of guessing
            report["github"] = {"not_run": f"{type(exc).__name__}: {exc}"}
    return report


def to_markdown(report: dict) -> str:
    lines = ["# Repository review", "",
             f"Hard findings: **{report['hard_finding_count']}** "
             "(0 means every structural rule holds).", ""]
    for name, value in report["hard_findings"].items():
        if isinstance(value, dict):
            status = "ok" if not value["new"] and not value["gone"] else \
                f"new {value['new']} · gone {value['gone']}"
        else:
            status = "ok" if not value else ", ".join(map(str, value))
        lines.append(f"- `{name}`: {status}")
    lay, size = report["layering"], report["size"]
    lines += ["", "## Layering",
              f"{lay['packages']} packages, {lay['edges']} cross-package import edges, "
              f"{lay['two_way_pairs_kept']} two-way pairs and "
              f"{lay['boundary_violations_kept']} boundary import kept by the ratchet.",
              "", "## Size",
              f"{size['python_files']} Python files outside tests, {size['python_lines']} lines, "
              f"median {size['median_file_lines']}; {size['files_over_1500_lines']} files over "
              "1,500 lines.", ""]
    lines += [f"- {f['path']}: {f['lines']}" for f in size["largest"]]
    dups = report["duplicates"]
    lines += ["", "## Duplicate function bodies (trend, not a gate)",
              f"{len(dups)} shapes of 10+ lines repeat across files, "
              f"{sum((len(g) - 1) * g[0]['lines'] for g in dups)} duplicated lines."]
    lines += ["- " + ", ".join(f"{x['path']}:{x['function']}" for x in g) for g in dups[:10]]
    g = report["gates"]
    lines += ["", "## Mutation gates",
              f"{g['scripts']} gate scripts, {g['anchors_checked']} literal anchors checked; "
              f"not statically checkable: {', '.join(g['not_statically_checkable']) or 'none'}."]
    for name, sites in g["multi_site_advisory"].items():
        lines += [f"- advisory, {name}: anchor occurs at {s['sites']} sites in {s['target']}"
                  for s in sites]
    if "lint" in report:
        lines += ["", "## Lint trend (ruff F, E9; never a gate)", f"{report['lint']}"]
    gh = report.get("github")
    if gh:
        lines += ["", "## Pull-request flow (SOP-06 proxies)", ""]
        lines += [f"- {k}: {v}" for k, v in gh.items()]
    lines += ["", "Review procedure and what to do with each finding: "
              "`docs/REVIEW_CADENCE.md`."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    ap.add_argument("--check", action="store_true", help="exit 1 on any hard finding")
    ap.add_argument("--github", metavar="OWNER/REPO", help="add PR-flow metrics (network)")
    ap.add_argument("--lint", action="store_true", help="add a ruff finding count (trend only)")
    args = ap.parse_args(argv)
    report = build_report(ROOT, args.github, lint=args.lint)
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else to_markdown(report))
    return 1 if args.check and report["hard_finding_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
