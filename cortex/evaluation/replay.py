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


class _Config:
    def __init__(self, model: str):
        self.model = model


class TranscriptClient:
    """Serves recorded replies; refuses anything it has no recorded reply for."""

    def __init__(self, replies: Mapping[str, str], *, model_label: str = "replayed-transcript"):
        if not isinstance(replies, Mapping) or not replies:
            raise ValueError("replay transcript is empty")
        self.config = _Config(model_label)   # what the semantic organ records as the model name
        for key, reply in replies.items():
            if not (isinstance(key, str) and len(key) == 64 and isinstance(reply, str)):
                raise ValueError("replay transcript must map 64-hex prompt keys to reply strings")
        self._replies = dict(replies)
        self.calls: list[str] = []
        self.misses: list[str] = []

    @classmethod
    def from_file(cls, path: str | Path, *, model_label: str = "replayed-transcript") -> "TranscriptClient":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != REPLAY_SCHEMA:
            raise ValueError(f"replay transcript schema must be {REPLAY_SCHEMA}")
        return cls(data["replies"], model_label=model_label)

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


def _cortex_with_semantic_client(client) -> Any:
    """A Cortex whose semantic organ is served by ``client``; every other organ is the default."""
    from ..routing import Cortex, SEMANTIC
    from ..organs.semantic import SemanticOrgan

    class ReplayCortex(Cortex):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.organs[SEMANTIC] = SemanticOrgan(client=client)
    return ReplayCortex


def run_replay(partition: str, arm_names: list[str], replies_path: str | Path,
               provenance: Mapping[str, Any], *, semantic_replies_path: str | Path | None = None) -> dict:
    prov = validate_provenance(provenance)
    label = str(prov["model"]).split(" (")[0].strip() or "replayed-transcript"
    client = TranscriptClient.from_file(replies_path, model_label=label)
    semantic_client = None
    original_cortex = R.Cortex
    try:
        if semantic_replies_path is not None:
            semantic_client = TranscriptClient.from_file(semantic_replies_path, model_label=label)
            R.Cortex = _cortex_with_semantic_client(semantic_client)
        results = R.run(partition, arm_names, client_factory=lambda: client)
    finally:
        R.Cortex = original_cortex
    replayed = [a for a in arm_names if a in ("always_llm", "llm_committee")]
    results["arm_provenance"] = {
        "schema": "cortex-arm-provenance/0.1",
        "replayed_arms": replayed,
        "transcript_sha256": "sha256:" + hashlib.sha256(Path(replies_path).read_bytes()).hexdigest(),
        "prompts_served": len(client.calls), "prompts_missing": len(client.misses),
        "semantic_route": ({"served_by": "the same recorded model as the baselines (as the frozen arm "
                                         "disclosure pre-registers)",
                            "transcript_sha256": "sha256:" + hashlib.sha256(
                                Path(semantic_replies_path).read_bytes()).hexdigest(),
                            "prompts_served": len(semantic_client.calls),
                            "prompts_missing": len(semantic_client.misses)}
                           if semantic_client is not None else
                           {"served_by": "no model; the semantic organ reports DEPENDENCY_UNAVAILABLE and the "
                                         "routed seed abstains on sourced items"}),
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
    ap.add_argument("--semantic-answers", help="optional transcript serving the routed seed's semantic organ (same model as the baselines)")
    ap.add_argument("--partition", choices=sorted(R.SUITES), default="smoke")
    ap.add_argument("--arms", default="routed_seed,always_llm,llm_committee,always_abstain")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    provenance = json.loads(Path(args.provenance).read_text(encoding="utf-8"))
    results = run_replay(args.partition, [a for a in args.arms.split(",") if a], args.answers, provenance,
                         semantic_replies_path=args.semantic_answers)
    Path(args.out).write_text(json.dumps(results, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    brief = {k: (v.get("status"), v.get("summary", {}).get("mean_quality"),
                 v.get("summary", {}).get("critical_errors"), v.get("reason"))
             for k, v in results["arms"].items()}
    print(json.dumps({"partition": args.partition, "arms": brief, "exit": results["exit"],
                      "prompts_missing": results["arm_provenance"]["prompts_missing"],
                      "semantic_route": results["arm_provenance"]["semantic_route"]}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
