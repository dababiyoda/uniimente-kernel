"""Review round 2 on #213: edit a recorded answer while keeping its total, flag and summary, and run the
recorded-run test on it. Usage, from the repository root:

    git show b4c9fa4c:tests/integration/test_greg_transfer_eval.py > /tmp/old_test.py
    PYTHONPATH=. python docs/evidence/greg-transfer/2026-10-28/review-round-2-mutants.py \
        /tmp/old_test.py tests/integration/test_greg_transfer_eval.py

Each test copy runs with ROOT pinned to this repository and EVIDENCE pointed at an edited copy of results.json;
the committed results.json is never written."""
import copy, importlib.util, json, re, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
base = json.loads((ROOT / "docs/evidence/greg-transfer/2026-10-28/results.json").read_text())


def mutants():
    m = copy.deepcopy(base); m["raw"]["tasks"][0]["experienced"]["task"]["answer"]["assignment"][0][2] = 1
    yield "Ana 2->1, total kept", m
    m = copy.deepcopy(base); m["raw"]["tasks"][0]["experienced"]["task"]["answer"]["assignment"][2][1] = "Dock1"
    yield "Cy moved to an order Cy is not eligible for", m
    m = copy.deepcopy(base); m["raw"]["tasks"][0]["control"]["task"]["answer"]["unfilled"] = {"Dock1": 1}
    yield "control's unfilled order rewritten", m
    t = next(i for i, r in enumerate(base["raw"]["tasks"]) if r["tier"] == "cross_family")
    m = copy.deepcopy(base); p = m["raw"]["tasks"][t]["experienced"]["task"]["answer"]["pairs"]
    p[0][1], p[1][1] = p[1][1], p[0][1]
    yield "matching pairs swapped (size kept)", m
    t = next(i for i, r in enumerate(base["raw"]["tasks"]) if r["tier"] == "unrelated")
    m = copy.deepcopy(base); m["raw"]["tasks"][t]["experienced"]["task"]["answer"]["schedule"][0][1] += 1
    yield "crash schedule start shifted (cost kept)", m


def load(label: str, path: str):
    source = re.sub(r"^ROOT = .*$", f"ROOT = Path({str(ROOT)!r})", Path(path).read_text(), count=1, flags=re.M)
    staged = Path(tempfile.mkdtemp()) / "staged_test.py"
    staged.write_text(source)
    spec = importlib.util.spec_from_file_location(f"t_{label}", staged)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


for label, path in (("old (b4c9fa4c)", sys.argv[1]), ("new", sys.argv[2])):
    mod = load(label[:3], path)
    for name, doc in mutants():
        d = Path(tempfile.mkdtemp())
        (d / "results.json").write_text(json.dumps(doc))
        mod.EVIDENCE = d
        try:
            mod.test_the_recorded_run_re_derives_from_its_own_rows()
            verdict = "PASSES (edit not caught)"
        except Exception as e:  # noqa: BLE001 - the verdict is the exception
            verdict = f"FAILS: {type(e).__name__}: {str(e)[:90]}"
        print(f"{label:15} | {name:46} | {verdict}")
