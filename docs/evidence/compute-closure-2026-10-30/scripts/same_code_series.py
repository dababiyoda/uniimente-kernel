"""LOCAL-REAL: `greg compute benchmark` N times on the same code, one after another, then `greg compute verify` on
every consecutive pair. Every VERIFIED here is a false positive. Each pair is also scored by the statistics alone
(p <= alpha and effect above the before run's noise floor), the verdict before the contention guard.
Usage: python -B same_code_series.py OUT_DIR [N] > same-code-series.json"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
out_dir, n = Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 10
out_dir.mkdir(parents=True, exist_ok=True)
nobody = out_dir / "no-body-home"                       # the CLI refuses --out inside a body home; none exists here


def greg(*args):
    run = subprocess.run([sys.executable, "-B", "-m", "greg", "--home", str(nobody), "compute", *args], cwd=ROOT,
                         capture_output=True, text=True, check=True, env={"PYTHONDONTWRITEBYTECODE": "1",
                                                                          "PATH": "/usr/bin:/bin"})
    return json.loads(run.stdout)


runs = []
for i in range(n):
    path = out_dir / f"run-{i:02d}.json"
    greg("benchmark", "--out", str(path))
    data = json.loads(path.read_text())
    runs.append({"file": path.name, "median_seconds": data["median_seconds"], "relative_iqr": data["relative_iqr"],
                 "contention_medians": data["contention"]["medians"],
                 "load1_start": data["host"]["conditions"]["load1"],
                 "load1_end": data["host"]["conditions_at_end"]["load1"]})
pairs = []
for i in range(n - 1):
    v = greg("verify", "--before", str(out_dir / runs[i]["file"]), "--after", str(out_dir / runs[i + 1]["file"]))
    stats_only = ("VERIFIED" if v.get("p_value") is not None and v["p_value"] <= v["alpha"]
                  and v["relative_effect"] > v["noise_floor"] else "not verified")
    pairs.append({"before": runs[i]["file"], "after": runs[i + 1]["file"], "verdict": v["verdict"],
                  "statistics_only": stats_only, "p_value": v.get("p_value"),
                  "relative_effect": v.get("relative_effect"), "noise_floor": v.get("noise_floor"),
                  "contention_shift": v["contention"].get("shift"), "reason": v["reason"]})
summary = {"runs": n, "pairs": len(pairs),
           "verified_with_guard": sum(p["verdict"] == "VERIFIED" for p in pairs),
           "inconclusive_with_guard": sum(p["verdict"] == "INCONCLUSIVE" for p in pairs),
           "verified_by_statistics_only": sum(p["statistics_only"] == "VERIFIED" for p in pairs)}
print(json.dumps({"summary": summary, "runs": runs, "pairs": pairs}, indent=1))
