"""The developmental invariant, as a reusable checker.

    No cell may access the complete target structure, receive a centrally
    assigned final fate, or use privileged omniscient state.

Three clauses, each independently checkable. This replaces an earlier and
wrong formulation ("if any component reads global state, there is no
morphogenesis"), which was too absolute: it would have disqualified the
Bicoid gradient, Wolpert positional information, Spemann organiser boundary
cues, and Levin's long-range bioelectric coupling — that is, most of actual
development.

LEGITIMATE developmental inputs, explicitly permitted:
  - local morphogen fields sampled at the cell's own location
  - tissue-scale gradients arising from diffusion and boundary sources
  - accumulated signals (a cell's own history)
  - boundary conditions and organiser regions
  - long-range signalling, including electrical coupling

PROHIBITED:
  - reading a stored target morphology (the blueprint)
  - having a final fate written by anything other than the cell's own dynamics
  - unbounded input arity: seeing the whole tissue rather than a sample of it

The distinction is not range. It is omniscience and assignment. A gradient
spanning the entire embryo is fine; a lookup table from address to fate is
not.
"""

import ast

# Names that would let a cell compute fate directly from an address rather
# than from what it can sense at its location. Absolute coordinates in a
# known-size lattice are equivalent to a blueprint lookup, which is why they
# are a sound proxy for clause 1 even though "position" per se is legitimate
# developmental information.
_ADDRESS_NAMES = {
    "x", "y", "idx", "index", "position", "pos", "coord", "coords",
    "row", "col", "width", "height", "grid", "lattice", "substrate",
}

# Modules whose presence would give a cell omniscient or authority-bearing
# reach.
_FORBIDDEN_IMPORTS = {
    "substrate", "policy", "authority", "capital", "provenance",
    "constitution", "identity", "capabilities",
}

# Function-name fragments implying a prewritten recovery path.
_REPAIR_NAMES = ("wound", "repair", "regenerate", "restore", "heal", "damaged", "rescue")


def _parse(path):
    with open(path) as handle:
        return ast.parse(handle.read())


def imported_modules(path):
    tree = _parse(path)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.split(".")[0])
            if node.level:
                for alias in node.names:
                    found.add(alias.name.split(".")[0])
    return found


def clause1_no_target_structure(path):
    """No blueprint: the module may not reach the substrate, and may not hold
    a stored target morphology."""
    violations = []

    reached = imported_modules(path) & _FORBIDDEN_IMPORTS
    if reached:
        violations.append(f"imports {sorted(reached)}")

    # A module-level container of non-trivial length is a candidate blueprint.
    tree = _parse(path)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(
                    node.value, (ast.List, ast.Tuple, ast.Dict, ast.Set)
                ):
                    size = len(getattr(node.value, "elts", None) or
                               getattr(node.value, "keys", []))
                    if size > 8:
                        violations.append(
                            f"module-level container {target.id} of size {size} "
                            f"— candidate stored morphology"
                        )
    return violations


def clause2_no_assigned_fate(path):
    """No externally written fate: nothing in the module may set a cell's type
    from outside its own dynamics, and no prewritten repair path may exist."""
    violations = []
    tree = _parse(path)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            lowered = node.name.lower()
            if any(frag in lowered for frag in _REPAIR_NAMES):
                violations.append(f"prewritten recovery routine {node.name}()")
            if lowered.startswith(("set_fate", "assign_", "designate_")):
                violations.append(f"external fate assignment {node.name}()")
    return violations


def clause3_no_omniscient_state(path, function_name, max_arity=12):
    """No omniscience: the named update function may not take an address, and
    its input arity must be bounded — a cell samples its surroundings, it does
    not receive the tissue."""
    violations = []
    tree = _parse(path)
    target = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == function_name),
        None,
    )
    if target is None:
        return [f"{function_name}() not found"]

    names = {a.arg for a in target.args.args}
    offending = names & _ADDRESS_NAMES
    if offending:
        violations.append(f"{function_name}() takes address args {sorted(offending)}")

    if len(target.args.args) > max_arity:
        violations.append(
            f"{function_name}() arity {len(target.args.args)} exceeds {max_arity} "
            f"— receiving tissue rather than sampling it"
        )
    if target.args.vararg is not None:
        violations.append(f"{function_name}() takes *{target.args.vararg.arg} — unbounded input")
    return violations


def check(path, function_name):
    """Run all three clauses. Returns a list of violations; empty means the
    invariant holds for this module."""
    return (
        clause1_no_target_structure(path)
        + clause2_no_assigned_fate(path)
        + clause3_no_omniscient_state(path, function_name)
    )
