"""Freeze what Ollama's own code serves for every store scenarios.py writes, into answers.json.

    sh tests/fixtures/ollama_oracle/build_oracle.sh <oracle-dir>
    python -B -I tests/fixtures/ollama_oracle/freeze.py <oracle-dir>

Each scenario is built in a fresh directory and both oracles (Ollama v0.40.0 0d0720e and main e9fde36d, see
build_oracle.sh) are asked for its request name with no runner and with each runner, with HOME=<dir> unless
scenarios.HOME names another (None: unset) and OLLAMA_MODELS as scenarios.ENV says (<dir>/models unless it names
another spelling; None: unset). A temporary directory's path in an error is written as <dir>, and an oracle that
panics (Ollama's envconfig.Models without a HOME) is recorded by its panic line, since its stack trace varies. Run it on Linux: with no runner, Ollama orders the runners by platform.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLLAMA = {"v040": "0d0720e51fb2fd9aa58781c3d720c06d720c2e7b", "main": "e9fde36d75fea66579d84099956ce1430792737a"}
RUNNERS = ("", "mlx", "llamacpp", "ggml")


def load_scenarios():
    spec = importlib.util.spec_from_file_location("ollama_oracle_scenarios", HERE / "scenarios.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def models_env(scenarios, scenario: str, directory: Path) -> str | None:
    """The OLLAMA_MODELS value a scenario runs under (scenarios.ENV, "{models}" standing for <dir>/models; None:
    unset)."""
    value = scenarios.ENV.get(scenario, "{models}")
    return None if value is None else value.replace("{models}", str(directory / "models"))


def home_env(scenarios, scenario: str, directory: Path) -> str | None:
    """The HOME a scenario runs under (scenarios.HOME, "{dir}" standing for <dir>; None: unset)."""
    value = getattr(scenarios, "HOME", {}).get(scenario, "{dir}")
    return None if value is None else value.replace("{dir}", str(directory))


def ask(binary: Path, directory: Path, name: str, runner: str, models: str | None, home: str | None) -> dict:
    env = {"PATH": os.environ.get("PATH", ""), "OLLAMA_MODELS": models, "HOME": home}
    env = {key: value for key, value in env.items() if value is not None}
    out = subprocess.run([str(binary), name, runner], capture_output=True, text=True, env=env, timeout=60)
    try:
        answer = json.loads(out.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        panic = next((line for line in out.stderr.splitlines() if line.startswith("panic: ")), None)
        answer = {"error": "oracle crashed: " + (panic or out.stderr.strip()[-200:] or out.stdout[-200:])}
    answer.pop("version", None)
    if "error" in answer:
        answer["error"] = answer["error"].replace(str(directory), "<dir>")
    return answer


def main() -> int:
    oracles = {v: Path(sys.argv[1]) / f"oracle-{v}.bin" for v in OLLAMA}
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "answers.json"
    scenarios = load_scenarios()
    go = shutil.which("go")
    frozen = {"provenance": {
        "ollama": {v: f"https://github.com/ollama/ollama/tree/{c}" for v, c in OLLAMA.items()},
        "oracle_template_sha256": sha256(HERE / "oracle.go.in"),
        "build_script_sha256": sha256(HERE / "build_oracle.sh"),
        "oracle_sha256": {v: sha256(p) for v, p in oracles.items()},
        "oracle_go": {v: subprocess.run([go, "version", str(p)], capture_output=True, text=True).stdout.split(": ")[-1]
                      .strip() if go else "unknown" for v, p in oracles.items()},
        "platform": f"{platform.system().lower()}/{platform.machine()}",
        "frozen": datetime.date.today().isoformat(),
        "runs": "<version>/<runner>, '-' for no runner", "freeze": "tests/fixtures/ollama_oracle/freeze.py"},
        "scenarios": {}}
    for fn in scenarios.SCENARIOS:
        directory = Path(tempfile.mkdtemp(prefix="ollama-oracle-"))
        try:
            (directory / "models").mkdir()
            got = fn(directory / "models")
            name, label, relays = got[0], got[1], list(got[2] if len(got) > 2 else ())
            fingerprint = scenarios.fingerprint(directory)      # before the oracles: v0.40.0 creates manifests/
            served, runs = [], {}
            for v in OLLAMA:
                for r in RUNNERS:
                    answer = ask(oracles[v], directory, name, r, models_env(scenarios, fn.__name__, directory),
                                 home_env(scenarios, fn.__name__, directory))
                    if answer not in served:
                        served.append(answer)
                    runs[f"{v}/{r or '-'}"] = served.index(answer)
            frozen["scenarios"][fn.__name__] = {"request": name, "label": label, "relays": relays,
                                                "ollama_models": scenarios.ENV.get(fn.__name__, "{models}"),
                                                "fingerprint": fingerprint, "runs": runs,
                                                "served": served}
            if fn.__name__ in getattr(scenarios, "HOME", {}):
                frozen["scenarios"][fn.__name__]["home"] = scenarios.HOME[fn.__name__]
        finally:
            shutil.rmtree(directory)
    out_path.write_text(dump(frozen), encoding="utf-8")
    print(f"{len(frozen['scenarios'])} scenarios frozen to {out_path}")
    return 0


def dump(frozen: dict) -> str:
    """answers.json: one scenario field per line and one answer per line, so a re-freeze diffs by answer."""
    line = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    out = ['{"provenance": ' + json.dumps(frozen["provenance"], indent=1, sort_keys=True), ' ,"scenarios": {']
    for i, (name, s) in enumerate(sorted(frozen["scenarios"].items())):
        out.append(f'  {"," if i else " "}{line(name)}: {{')
        out += [f'   {"," if j else " "}{line(key)}: {line(s[key])}'
                for j, key in enumerate(k for k in ("request", "label", "relays", "ollama_models", "home",
                                                    "fingerprint", "runs") if k in s)]
        out.append('   ,"served": [')
        out += [f'    {"," if j else " "}{line(answer)}' for j, answer in enumerate(s["served"])]
        out.append("   ]}")
    out.append(" }}")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    sys.exit(main())
