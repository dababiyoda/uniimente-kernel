"""Dump every code binding the Mind's evidence index is compared with, as computed on this tree. cwd = tree."""
import json, sys
sys.path.insert(0, ".")
from greg.cognition import compiler, code_binding
from greg.cognition.composition import RECIPES
from greg.cognition.catalog import FAMILIES
from greg.cognition.genomes import library
ev = compiler.evidence_index()
out = {"recipes": {}, "families": {}, "boundary": {}}
for recipe in sorted(set(RECIPES) | set(ev.get("recipes") or {})):
    verdict = (ev.get("recipes") or {}).get(recipe) or {}
    try:
        now = compiler.recipe_code(recipe)
    except Exception as exc:
        now = {"error": repr(exc)}
    out["recipes"][recipe] = {"now": compiler._recipe_code_now(recipe) if recipe in RECIPES else None,
                              "stale": compiler.recipe_stale(recipe, verdict) if verdict else "no verdict",
                              "status": verdict.get("status") or verdict.get("verdict"),
                              "members": (now or {}).get("closure_members")}
fams = sorted(set(FAMILIES) | set(library.executables()) | set(ev.get("operations") or {}) | set(ev.get("genomes") or {}))
for f in fams:
    try:
        st = compiler.family_status(f, ev)
    except Exception as exc:
        st = {"error": repr(exc)}
    sc = None
    try:
        sc = compiler.solver_code(f)
    except Exception as exc:
        sc = {"error": repr(exc)}
    gc = None
    try:
        gc = compiler.genome_code(f)
    except Exception as exc:
        gc = {"error": repr(exc)}
    out["families"][f] = {"status": {k: st.get(k) for k in ("status", "raw", "stale", "kind")} if isinstance(st, dict) else st,
                          "solver_closure": (sc or {}).get("closure_sha256"), "solver_sha": (sc or {}).get("sha256"),
                          "genome_closure": (gc or {}).get("sha256")}
for path, name in (("greg/cognition/cortex.py", "reason"), ("greg/cognition/bridge.py", "reason_cortex"),
                   ("greg/cognition/compiler.py", "run"), ("greg/cognition/cortex.py", "_numeric"),
                   ("greg/cognition/cortex.py", "independent_verify"), ("greg/cognition/bridge.py", "run_worker")):
    b = code_binding.closure(path, name)
    out["boundary"][f"{path}::{name}"] = None if b is None else {"sha256": b["sha256"], "n_members": len(b["members"])}
    txt = open(path).read()
    out["boundary"][f"{path}::{name}"] = {**(out["boundary"][f"{path}::{name}"] or {}), "function_digest": compiler.function_digest(txt, name)}
json.dump(out, open(sys.argv[1], "w"), indent=1, sort_keys=True)
print("recipes", len(out["recipes"]), "families", len(out["families"]))
