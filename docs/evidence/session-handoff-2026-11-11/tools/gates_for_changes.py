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
