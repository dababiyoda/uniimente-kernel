"""Fixed CMC appraisal, separate from Linker and from the mission coordinator.

No worker-provided evaluator callback, plugin, score, veto override or code path.
This re-derives the narrow expected result from raw evidence, not the worker's
success assertion. Same-host privileged compromise is explicitly out of scope.
"""
from __future__ import annotations

from hashlib import sha256
import json

from jsonschema import Draft202012Validator
import yaml

from omnimorph.organization_compiler import content_digest

LIMITATION = "Declared route only; current-main interoperability was not executed."
PIN_DISSENT = "Older manifest pins may be intentional; do not update them automatically."
RESULT_FIELDS = {"route", "declared_route_present", "revisions", "source_digests",
                 "actual_organ_execution"}


def appraise(snapshot: dict, result: dict) -> dict:
    """Recompute claims using an evidence copy. This cannot authorize any act."""
    errors = []
    try:
        if set(result) != RESULT_FIELDS:
            raise ValueError("unknown or missing result fields")
        corpus = snapshot["corpus"]
        raw = snapshot["source_texts"]
        if set(raw) != set(corpus["source_hashes"]):
            raise ValueError("missing or extra source evidence")
        hashes = {path: "sha256:" + sha256(text.encode()).hexdigest()
                  for path, text in raw.items()}
        if hashes != corpus["source_hashes"]:
            raise ValueError("corrupt source evidence")
        producer = yaml.safe_load(raw["organs/daleobanks.manifest.yaml"])
        consumer = yaml.safe_load(raw["organs/wealthmachine.manifest.yaml"])
        schema = json.loads(raw["contracts/wire-opportunity-packet.schema.json"])
        Draft202012Validator.check_schema(schema)
        route = corpus["expected_route"]
        revisions = [
            {"repository": item["repository"], "manifest_pin": item["source"]["commit"],
             "observed_main": corpus["observed_main_revisions"][item["repository"]],
             "matches": item["source"]["commit"] == corpus["observed_main_revisions"][item["repository"]]}
            for item in (producer, consumer)
        ]
        expected = {
            "route": route,
            "declared_route_present": (producer["organ_id"] == route["producer"]
                and consumer["organ_id"] == route["consumer"]
                and route["contract"] in producer["contracts"]["produces"]
                and route["contract"] in consumer["contracts"]["consumes"]),
            "revisions": revisions, "source_digests": hashes,
            "actual_organ_execution": False,
        }
        if content_digest(result) != content_digest(expected):
            raise ValueError("worker result differs from independently derived evidence")
        if not expected["declared_route_present"]:
            raise ValueError("required declared route is absent")
    except (KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    report = {
        "verifier": "verifier.mission_audit.appraise",
        "accepted": not errors, "errors": errors,
        "result_digest": content_digest(result),
        "snapshot_digest": content_digest(snapshot),
        "dissent": [LIMITATION, PIN_DISSENT],
        "execution_authority": "none",
    }
    report["digest"] = content_digest(report)
    return report
