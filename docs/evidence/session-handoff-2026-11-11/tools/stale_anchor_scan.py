"""Which strings in the mutation-gate scripts occur in a changed file at the base and no longer at the head?
usage: stale_anchor_scan.py <worktree> <base-commit>     (read-only; a heuristic, not a gate)"""
import ast, subprocess, sys
from pathlib import Path
wt, base = Path(sys.argv[1]), sys.argv[2]
git = lambda *a: subprocess.run(["git", "-C", str(wt), *a], capture_output=True, text=True).stdout
changed = [f for f in git("diff", "--name-only", base, "HEAD").split() if not f.startswith(("tests/", "scripts/ci/", "docs/"))]
found = 0
for f in changed:
    old, new = git("show", f"{base}:{f}"), (wt / f).read_text() if (wt / f).exists() else ""
    if not old:
        continue
    for gate in sorted((wt / "scripts" / "ci").glob("check_*mutant*.py")):
        seen = set()
        for node in ast.walk(ast.parse(gate.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) >= 16:
                s = node.value
                if s in seen or s.endswith(".py") or "/" in s and "\n" not in s and " " not in s:
                    continue
                seen.add(s)
                if old.count(s) >= 1 and new.count(s) != 1 and new.count(s) != old.count(s):
                    found += 1
                    print(f"{gate.name}: in {f} base x{old.count(s)} head x{new.count(s)}: {s[:110]!r}")
print("changed product files:", changed)
print("suspect anchors:", found)
