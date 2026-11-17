"""Section 16 venture case on the real organs, through the body's signed-mission entry point. Writes evidence."""
import json
import subprocess
import sys
from pathlib import Path

out_dir, rs, wmi = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, ".")
from greg.body import Body, Layout  # noqa: E402
from greg.templates import venture_assessment  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402
from tests.unit.test_greg_ventures import ECONOMICS, RANDOMIZED  # noqa: E402
import tempfile  # noqa: E402

head = lambda p: subprocess.run(["git", "-C", str(p), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
log = [f"kernel head: {head(Path('.'))}", f"railscout head: {head(rs)} ({rs})", f"wealthmachine head: {head(wmi)} ({wmi})", ""]
signal = rs / "examples" / "project-source-packet"
for name, economics in (("observational", ECONOMICS), ("randomized", RANDOMIZED)):
    with tempfile.TemporaryDirectory() as tmp:
        home, key, body_id, _ = make_body(Path(tmp), read_roots=[rs, wmi])
        spec = venture_assessment(railscout_root=str(rs), wmi_root=str(wmi), manifest=str(signal / "manifest.json"),
                                  source_root=str(signal), economics=economics, preauthorize_delivery=True)
        drop(home, signed(key, body_id, "MISSION", spec))
        clock, states = Clock(), []
        with Body(home, clock=clock) as body:
            body.boot()
            for _ in range(8):
                clock.advance(30)
                states.append(body.tick()["missions"][0]["state"])
                if states[-1] == "ACHIEVED":
                    break
            appraisal = body.journal.replay("mission.appraised")[-1].payload
            memo_path = next((Layout(home).home / "deliveries" / "ventures").glob("venture-*.md"))
            memo = memo_path.read_text()
            receipts = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                        if isinstance(r.payload["result"].get("output"), dict)
                        and str(r.payload["result"]["output"].get("problem_id", "")).startswith("venture-")]
        (out_dir / f"memo-{name}.md").write_text(memo)
        log += [f"== {name} causal support ({economics['causal_support']['design']})",
                f"mission states: {states}",
                f"appraisal: {appraisal['verdict']}; findings: {appraisal.get('findings')}",
                *[f"cognition receipt {r['problem_id'].split('-')[1]}: {r['method']} {r['method_version']}, "
                  f"abstention_state {r['abstention_state']}, authority_created {r['authority_created']}"
                  for r in receipts],
                "memo revenue section:", *[f"  {line}" for line in
                                          memo.split("## Revenue", 1)[1].split("\n## ", 1)[0].strip().splitlines()],
                ""]
(out_dir / "real-organs-mission.log").write_text("\n".join(log) + "\n")
print("\n".join(log))
