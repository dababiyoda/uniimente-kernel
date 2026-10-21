"""The Seed Genome's scope boundaries from the 2026-10-13 directive, made executable.

"Keep MICA/CDPE completely outside" (MICA and CDPE live in ``developmental/``): no module of the
cortex imports the developmental substrate, the literal morphogenesis lineage or OMNIMORPH, and
running a receipt end to end loads none of them. Reserved developmental families stay registered,
disabled and ineligible (tested in test_cortex_gates_genome.py); this test pins the code boundary.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTSIDE = ("developmental", "morphogenesis", "omnimorph")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def test_no_cortex_module_imports_the_developmental_substrate():
    files = sorted((ROOT / "cortex").rglob("*.py")) + [ROOT / "egregore/cortex_proposer.py"]
    assert len(files) > 15
    offenders = {str(f.relative_to(ROOT)): sorted(_imports(f) & set(OUTSIDE)) for f in files}
    assert not {k: v for k, v in offenders.items() if v}


def test_a_receipt_end_to_end_loads_none_of_them():
    code = ("import sys, json; from cortex.routing import Cortex; "
            "r = Cortex(clock=lambda: '2026-10-14T00:00:00Z').run({'problem_id': 'b', 'question': 'q', 'payload': {"
            "'estimation_model': {'target': {'name': 'c', 'unit': 'USD/week'}, 'expression': ['*', 'h', 'r'], "
            "'variables': [{'name': 'h', 'unit': 'hour/week', 'low': 30, 'high': 50}, "
            "{'name': 'r', 'unit': 'USD/hour', 'low': 40, 'high': 60}]}, "
            "'declared': {'consequence_class': 'internal_write', 'reversibility': 'reversible'}}}); "
            "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules})))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    loaded = set(__import__("json").loads(out.stdout))
    assert "cortex" in loaded
    assert not loaded & set(OUTSIDE), sorted(loaded & set(OUTSIDE))
