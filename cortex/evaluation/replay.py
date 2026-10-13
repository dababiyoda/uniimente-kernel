"""Replay client: run the frozen baseline arms from a transcript of model replies.

The seed's declared baselines (``always_llm``, ``llm_committee``) call
``client.complete(system_prompt, user_prompt)``. When no model is reachable from
the evaluation process, the arms are ``NOT_RUN`` and the exit stays
``INCONCLUSIVE``. This module lets the SAME frozen harness, scorer and exit rule
run those arms from replies that a model produced elsewhere, under these rules:

* a reply is looked up by the SHA-256 of ``system_prompt + "\\0" + user_prompt``,
  so a reply can only be used for the exact prompt the frozen arm would have
  sent; a missing reply is an error on that item, never a guess;
* the harness's frozen inputs are untouched (this file is not in the freeze
  manifest and changes nothing the manifest hashes), so the held-out partition
  still refuses to run if any frozen input changed;
* the model's identity, how it was invoked, and every limitation of the
  transcript are recorded on the results under ``arm_provenance`` and replace
  the harness's local-model resource disclosure for the replayed arms.

A transcript proves nothing about a model that was not actually asked. It is a
record of replies, not a simulation of them.

    python -m cortex.evaluation.replay --answers replies.json --provenance prov.json \
        --partition heldout --out results.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from . import run as R

PROBE_SYSTEM = "Return {\"ok\": true} as JSON."
PROBE_USER = "{}"
REPLAY_SCHEMA = "cortex-replay-transcript/0.1"
REQUIRED_PROVENANCE = ("model", "invocation", "tool_use", "prompt_fidelity", "limitations")


def prompt_key(system_prompt: str, user_prompt: str) -> str:
    return hashlib.sha256((system_prompt + "\x00" + user_prompt).encode("utf-8")).hexdigest()


class TranscriptClient:
    """Serves recorded replies; refuses anything it has no recorded reply for."""

    def __init__(self, replies: Mapping[str, str]):
        if not isinstance(replies, Mapping) or not replies:
            raise ValueError("replay transcript is empty")
        for key, reply in replies.items():
            if not (isinstance(key, str) and len(key) == 64 and isinstance(reply, str)):
                raise ValueError("replay transcript must map 64-hex prompt keys to reply strings")
        self._replies = dict(replies)
        self.calls: list[str] = []
        self.misses: list[str] = []

    @classmethod
    def from_file(cls, path: str | Path) -> "TranscriptClient":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != REPLAY_SCHEMA:
            raise ValueError(f"replay transcript schema must be {REPLAY_SCHEMA}")
        return cls(data["replies"])

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if (system_prompt, user_prompt) == (PROBE_SYSTEM, PROBE_USER):
            return "{\"ok\": true}"
        key = prompt_key(system_prompt, user_prompt)
        self.calls.append(key)
        if key not in self._replies:
            self.misses.append(key)
            raise ValueError(f"no recorded reply for prompt {key[:12]}; the item is scored as an error")
        return self._replies[key]


def validate_provenance(prov: Mapping[str, Any]) -> dict:
    missing = [k for k in REQUIRED_PROVENANCE if not prov.get(k)]
    if missing:
        raise ValueError(f"arm provenance is missing {missing}")
    return dict(prov)


def run_replay(partition: str, arm_names: list[str], replies_path: str | Path,
               provenance: Mapping[str, Any]) -> dict:
    prov = validate_provenance(provenance)
    client = TranscriptClient.from_file(replies_path)
    results = R.run(partition, arm_names, client_factory=lambda: client)
    replayed = [a for a in arm_names if a in ("always_llm", "llm_committee")]
    results["arm_provenance"] = {
        "schema": "cortex-arm-provenance/0.1",
        "replayed_arms": replayed,
        "transcript_sha256": "sha256:" + hashlib.sha256(Path(replies_path).read_bytes()).hexdigest(),
        "prompts_served": len(client.calls), "prompts_missing": len(client.misses),
        **prov,
    }
    disclosure = dict(results.get("resource_disclosure", {}))
    for arm in replayed:
        disclosure[arm] = (f"REPLAYED from a transcript: {prov['model']}; {prov['invocation']}; "
                           f"tool use: {prov['tool_use']}; the harness's local-model disclosure does not apply")
    results["resource_disclosure"] = disclosure
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--answers", required=True, help="replay transcript JSON (schema cortex-replay-transcript/0.1)")
    ap.add_argument("--provenance", required=True, help="JSON with model, invocation, tool_use, prompt_fidelity, limitations")
    ap.add_argument("--partition", choices=sorted(R.SUITES), default="smoke")
    ap.add_argument("--arms", default="routed_seed,always_llm,llm_committee,always_abstain")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    provenance = json.loads(Path(args.provenance).read_text(encoding="utf-8"))
    results = run_replay(args.partition, [a for a in args.arms.split(",") if a], args.answers, provenance)
    Path(args.out).write_text(json.dumps(results, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    brief = {k: (v.get("status"), v.get("summary", {}).get("mean_quality"),
                 v.get("summary", {}).get("critical_errors"), v.get("reason"))
             for k, v in results["arms"].items()}
    print(json.dumps({"partition": args.partition, "arms": brief, "exit": results["exit"],
                      "prompts_missing": results["arm_provenance"]["prompts_missing"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
