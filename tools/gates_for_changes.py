"""Which mutation gates mutate a file this branch changed? Those gates must be RUN before a push, not only scanned:
a mutant whose anchor still matches can lose the only test that reached it.
usage: gates_for_changes.py <worktree> <base-commit>      (read-only)"""
import ast, subprocess, sys
from pathlib import Path
wt, base = Path(sys.argv[1]), sys.argv[2]
out = subprocess.run(["git", "-C", str(wt), "diff", "--name-only", base, "HEAD"], capture_output=True, text=True).stdout
changed = {f for f in out.split() if f.endswith(".py") and not f.startswith(("tests/", "scripts/"))}
print("changed product files:", sorted(changed))
for gate in sorted((wt / "scripts" / "ci").glob("check_*mutant*.py")):
    tree = ast.parse(gate.read_text())
    consts = {}                                   # module-level NAME = "path" constants a gate uses for its targets
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = node.value.value
    hit = {}
    def scan(node, group):
        for sub in ast.walk(node):
            v = sub.value if isinstance(sub, ast.Constant) and isinstance(sub.value, str) else \
                consts.get(sub.id) if isinstance(sub, ast.Name) else None
            if v in changed:
                hit.setdefault(group, set()).add(v)
    groups = {}
    for node in tree.body:                         # check_cortex_mutants.py: NAME_MUTANTS lists, run group by group
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.endswith("MUTANTS") for t in node.targets):
            scan(node.value, [t.id for t in node.targets if isinstance(t, ast.Name)][0])
        else:
            scan(node, "(module)")
    if hit:
        named = {g: sorted(v) for g, v in hit.items() if g != "(module)"}
        print(f"RUN {gate.name}: " + ("; ".join(f"{g} -> {', '.join(v)}" for g, v in sorted(named.items())) if named
                                      else ", ".join(sorted(hit['(module)']))))


# --- stored patches a test keeps applicable (added 2026-11-12 after #300's CI failure) -------------------------
# A draft patch kept in the repository is another consumer of the file it patches. A test that asserts it still
# applies fails when a branch rewraps or moves the lines the patch is anchored on, and no test of the changed
# behaviour names it.
def _guarded_patches(worktree):
    import re as _re
    import subprocess as _sp
    from pathlib import Path as _P
    root = _P(worktree)
    found = set()
    for test in (root / "tests").rglob("test_*.py"):
        try:
            text = test.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in _re.finditer(r"[\"']([\w./-]+\.patch)[\"']", text):
            if (root / match.group(1)).is_file():
                found.add((match.group(1), str(test.relative_to(root))))
    for patch, test in sorted(found):
        check = _sp.run(["git", "-C", str(root), "apply", "--check", patch], capture_output=True, text=True)
        state = "applies" if check.returncode == 0 else "DOES NOT APPLY: " + check.stderr.strip().splitlines()[0]
        print(f"PATCH {patch} (kept applicable by {test}): {state}")


def _owned_source_inventory(worktree, base):
    """Another consumer of every new source file: foundry/owned-source.json must list each file under the trees it
    covers (tests/unit/test_greg_packaging.py compares it with foundry.systems.build._files). Seen 2026-11-12: #305
    added greg/intake.py and greg/intake_rehearsal.py and CI job 1 failed on the inventory, not on the unit."""
    import json as _json, subprocess as _sp
    root = Path(worktree)
    inv = root / "foundry" / "owned-source.json"
    if not inv.is_file():
        return
    listed = set(_json.loads(inv.read_text()).get("files", []))
    added = _sp.run(["git", "-C", str(root), "diff", "--name-only", "--diff-filter=AR", base, "HEAD"],
                    capture_output=True, text=True).stdout.split()
    untracked = _sp.run(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
                        capture_output=True, text=True).stdout.split()
    tops = {f.split("/")[0] for f in listed if "/" in f}
    for f in sorted(set(added) | set(untracked)):
        if "/" in f and f.split("/")[0] in tops and not f.startswith(("tests/", "docs/")) and f not in listed:
            print(f"INVENTORY {f}: not in foundry/owned-source.json (tests/unit/test_greg_packaging.py will fail)")


def _byte_pinned_records(worktree, base):
    """Records that pin a file's bytes (added 2026-11-12 after #309's CI failure): a one-line test fix failed CI twice,
    once because the Mind-lineage reconciliation map recorded the file as "kept" (byte-identical to a lineage head), and
    once because the data-exposure ledger, derived from committed files, counts a test fixture per lineage when its file
    differs between lineages. Neither is a mutation gate, so nothing above named them."""
    import json as _json, subprocess as _sp
    root = Path(worktree)
    diff = _sp.run(["git", "-C", str(root), "diff", "--name-only", base, "HEAD"], capture_output=True, text=True)
    files = set(diff.stdout.split())
    for m in sorted((root / "docs" / "collaboration").glob("MIND-LINEAGE-RECONCILIATION-MAP-*.json")):
        try:
            entries = _json.loads(m.read_text()).get("entries", [])
        except (OSError, ValueError):
            continue
        for e in entries:
            d = e.get("disposition", "")
            if e.get("path") in files and (d == "kept" or d.startswith("selected:")):
                print(f"PINNED {e['path']}: {m.name} records it as {d!r} (bytes of a lineage head); mark the entry "
                      "'modified' with a note, or tests/unit/test_greg_mind_convergence.py fails")
    ledger = root / "docs" / "evidence" / "greg-data-exposure-ledger.json"
    feeds = sorted(f for f in files if f.startswith("tests/") and f.endswith(".py") and (root / f).is_file()
                   and "instance" in (root / f).read_text(errors="replace"))
    if ledger.is_file() and feeds and "docs/evidence/greg-data-exposure-ledger.json" not in files:
        print("LEDGER test files that build instances changed (" + ", ".join(feeds) + "): run `PYTHONPATH=. python "
              "scripts/data_exposure_ledger.py --check` (about 6 min) and regenerate the ledger if it differs")


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1:
        _guarded_patches(_sys.argv[1])
    if len(_sys.argv) > 2:
        _owned_source_inventory(_sys.argv[1], _sys.argv[2])
        _byte_pinned_records(_sys.argv[1], _sys.argv[2])
