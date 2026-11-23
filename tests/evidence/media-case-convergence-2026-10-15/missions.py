"""Section 16 media case on the real DALEOBANKS checkout, through the body's signed-mission entry point."""
import subprocess
import sys
import tempfile
from pathlib import Path

out, dale = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, ".")
from tests.unit.test_greg_media_case import FAITHFUL, SOURCE, SPAN_DELAY, SPAN_FUEL, SPAN_NAME, SPAN_STUDY, run_mission  # noqa

head = lambda p: subprocess.run(["git", "-C", str(p), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
CASES = {
    "faithful": FAITHFUL,
    "hedge dropped": [{"text": "The routing method cuts delays by 12%.", "quotes": [SPAN_DELAY]}, FAITHFUL[1]],
    "negation removed": [FAITHFUL[0], {"text": "It lowered fuel costs.", "quotes": [SPAN_FUEL]}],
    "scope widened": [{"text": "All depots may see the routing method reduce delays by 12%.", "quotes": [SPAN_DELAY]}],
    "direction reversed": [{"text": "The new routing method may increase delays by 12%.", "quotes": [SPAN_DELAY]}],
    "name substituted": [{"text": "Drivers at Southgate reported fewer missed windows.", "quotes": [SPAN_NAME]}],
}
log = [f"kernel head: {head(Path('.'))}", f"daleobanks head: {head(dale)} ({dale})", f"source: {SOURCE}", ""]
for name, claims in CASES.items():
    with tempfile.TemporaryDirectory() as tmp:
        states, verdicts, _ = run_mission(Path(tmp), dale, claims)
    final = verdicts[-1] if verdicts else {}
    truth = final.get("truth_preservation") or {}
    log += [f"== {name}", "draft: " + " ".join(c["text"] for c in claims), f"mission states: {states}",
            f"daleobanks.verify: {final.get('verdict')}",
            f"DALEOBANKS EthicsGuard approved: {(final.get('daleobanks') or {}).get('ethics', {}).get('approved')}; "
            f"Critic blocking: {(final.get('daleobanks') or {}).get('critic', {}).get('blocking_issues')}",
            f"Mind's changes found: {[(d['claim'], d['class']) for d in truth.get('distortions', [])]}",
            *[f"finding: {f}" for f in final.get("findings", [])], ""]
(out / "real-daleobanks-missions.log").write_text("\n".join(log).rstrip("\n") + "\n")
print("\n".join(log))
