"""Worker-side Linker result for the frozen CMC fixture; no evaluator calls."""
from pathlib import Path
from linker.linker import InstitutionalLinker
from linker.manifest import load_manifest
from verifier.retained_appraisal import frozen_snapshot

ROOT = Path(__file__).resolve().parents[2]


def worker_result():
    snapshot = frozen_snapshot()
    corpus = snapshot["corpus"]
    manifests = [load_manifest(str(ROOT / p)) for p in (
        "organs/daleobanks.manifest.yaml", "organs/wealthmachine.manifest.yaml")]
    route = corpus["expected_route"]
    report = InstitutionalLinker(manifests, str(ROOT / "contracts")).link()
    return {
        "route": route,
        "declared_route_present": any(e.producer == route["producer"]
            and e.consumer == route["consumer"] and e.contract == route["contract"]
            for e in report.edges),
        "revisions": [{"repository": m.repository, "manifest_pin": m.raw["source"]["commit"],
            "observed_main": corpus["observed_main_revisions"][m.repository],
            "matches": m.raw["source"]["commit"] == corpus["observed_main_revisions"][m.repository]}
            for m in manifests],
        "source_digests": corpus["source_hashes"], "actual_organ_execution": False,
    }
