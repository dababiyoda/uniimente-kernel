"""Source-checkout CLI. Analysis only; never activate a capability or execute."""
import argparse
import json
import os
from pathlib import Path

from compiler.ucl_compiler import compile_constitution
from provenance.ledger import EvidenceLedger
from egregore.local_model import LocalModelClient
from .contracts import CognitiveRequest, GateAssessment
from .runtime import SeedCortex


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--suite", default="examples/cognition/seed-suite.json")
    benchmark.add_argument("--live-baselines", action="store_true")
    benchmark.add_argument("--out", required=True)
    solve = commands.add_parser("solve")
    solve.add_argument("--request", required=True)
    solve.add_argument("--gates", required=True, help="host policy/domain advisory assessment, never an execution grant")
    solve.add_argument("--ledger", required=True)
    solve.add_argument("--out", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    compiled = compile_constitution(root)
    with_ledger = EvidenceLedger(compiled.constitution_hash, getattr(args, "ledger", None))
    try:
        cortex = SeedCortex(with_ledger)
        if args.command == "benchmark":
            from .benchmark import load_suite, run_suite
            report = run_suite(cortex, load_suite(args.suite),
                               baseline_client=LocalModelClient() if args.live_baselines else None,
                               live_baselines=args.live_baselines)
        else:
            request = CognitiveRequest.from_dict(json.loads(Path(args.request).read_text()))
            gates = GateAssessment.from_dict(json.loads(Path(args.gates).read_text()))
            report = cortex.think(request, gates=gates).to_dict()
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Internal evidence may contain sensitive request material. Retain it
        # locally with owner-only permissions and never overwrite prior proof.
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(json.dumps({"output": str(target), "authority_created": False,
                          "promotion": report.get("promotion", "unpromoted")}))
    finally:
        with_ledger.close()


if __name__ == "__main__":
    main()
