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

The routed seed's semantic organ is always served by an injected client during
a replay (a second transcript with its own provenance, or a client that refuses),
so a reachable local model is never consulted silently. The injection rebinds
``cortex.evaluation.run.Cortex`` for the duration of one run and restores it in a
``finally``; replays are single-process, single-threaded by design.

    python -m cortex.evaluation.replay --answers replies.json --provenance prov.json \
        --partition heldout --out results.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from . import run as R

_HEX64 = re.compile(r"[0-9a-f]{64}")
PROBE_SYSTEM = "Return {\"ok\": true} as JSON."
PROBE_USER = "{}"
REPLAY_SCHEMA = "cortex-replay-transcript/0.1"
REQUIRED_PROVENANCE = ("model", "invocation", "tool_use", "prompt_fidelity", "limitations")
# Computed by the harness from the run itself; an operator record may not carry them.
RESERVED_PROVENANCE = ("schema", "replayed_arms", "transcript_sha256", "prompts_requested", "prompts_served",
                       "prompts_missing", "semantic_route", "declared_by_operator")


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
            if not (isinstance(key, str) and _HEX64.fullmatch(key) and isinstance(reply, str)):
                raise ValueError("replay transcript must map 64-hex prompt keys to reply strings")
        self._replies = dict(replies)
        self.requests: list[str] = []   # every lookup
        self.calls: list[str] = []      # lookups that were served
        self.misses: list[str] = []

    @classmethod
    def from_file(cls, path: str | Path, *, model_label: str = "replayed-transcript") -> "TranscriptClient":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, Mapping) or data.get("schema") != REPLAY_SCHEMA:
            raise ValueError(f"replay transcript schema must be {REPLAY_SCHEMA}")
        if "replies" not in data:
            raise ValueError("replay transcript has no 'replies'")
        return cls(data["replies"], model_label=model_label)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if (system_prompt, user_prompt) == (PROBE_SYSTEM, PROBE_USER):
            return "{\"ok\": true}"
        key = prompt_key(system_prompt, user_prompt)
        self.requests.append(key)
        if key not in self._replies:
            self.misses.append(key)
            raise ValueError(f"no recorded reply for prompt {key[:12]}; the item is scored as an error")
        self.calls.append(key)
        return self._replies[key]


class RefusingClient:
    """Stands in for the semantic organ's model when no semantic transcript is given, so a reachable
    local model can never be consulted silently during a replay: every call is DEPENDENCY_UNAVAILABLE."""

    def __init__(self):
        self.config = _Config("none (refusing client; no semantic transcript)")
        self.requests: list[str] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.requests.append(prompt_key(system_prompt, user_prompt))
        raise OSError("replay: no semantic transcript was supplied; the semantic organ has no model")


def validate_provenance(prov: Mapping[str, Any], *, semantic: bool = False) -> dict:
    if not isinstance(prov, Mapping):
        raise ValueError("arm provenance must be an object")
    missing = [k for k in REQUIRED_PROVENANCE if not prov.get(k)]
    if missing:
        raise ValueError(f"arm provenance is missing {missing}")
    clash = sorted(k for k in prov if k in RESERVED_PROVENANCE)
    if clash:
        raise ValueError(f"arm provenance may not declare harness-computed fields {clash}")
    if semantic:
        sem = prov.get("semantic_transcript")
        if not isinstance(sem, Mapping) or any(not sem.get(k) for k in ("model", "invocation", "tool_use")):
            raise ValueError("a semantic transcript needs its own provenance: semantic_transcript "
                             "{model, invocation, tool_use}")
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
    prov = validate_provenance(provenance, semantic=semantic_replies_path is not None)
    label = str(prov["model"]).split(" (")[0].strip() or "replayed-transcript"
    client = TranscriptClient.from_file(replies_path, model_label=label)
    if semantic_replies_path is not None:
        sem_label = str(prov["semantic_transcript"]["model"]).split(" (")[0].strip() or "replayed-transcript"
        semantic_client: Any = TranscriptClient.from_file(semantic_replies_path, model_label=sem_label)
    else:
        semantic_client = RefusingClient()
    original_cortex = R.Cortex
    try:
        # The routed seed's semantic organ is always served by an injected client during a replay:
        # a transcript, or a client that refuses. A reachable local model is never consulted silently.
        R.Cortex = _cortex_with_semantic_client(semantic_client)
        results = R.run(partition, arm_names, client_factory=lambda: client)
    finally:
        R.Cortex = original_cortex
    replayed = [a for a in arm_names if a in ("always_llm", "llm_committee")]
    if semantic_replies_path is not None:
        semantic_route = {
            "served_by": "transcript",
            "observed": {"prompts_requested": len(semantic_client.requests),
                         "prompts_served": len(semantic_client.calls),
                         "prompts_missing": len(semantic_client.misses),
                         "model_label_on_receipts": semantic_client.config.model},
            "transcript_sha256": "sha256:" + hashlib.sha256(Path(semantic_replies_path).read_bytes()).hexdigest(),
            "declared_by_operator": dict(prov["semantic_transcript"]),
        }
        routed_disclosure = (f"Python + z3 solver in-process; semantic route served by a recorded transcript "
                             f"({semantic_route['transcript_sha256'][:19]}…, declared model: "
                             f"{prov['semantic_transcript']['model']}); latency includes geometry, eligibility, "
                             f"gates, verification and receipt construction")
    else:
        semantic_route = {
            "served_by": "refusing_client",
            "observed": {"prompts_requested": len(semantic_client.requests),
                         "model_label_on_receipts": semantic_client.config.model},
            "note": "no semantic transcript: the semantic organ had no model and reported DEPENDENCY_UNAVAILABLE "
                    "on every sourced item it was asked (prompts_requested)",
        }
        routed_disclosure = ("Python + z3 solver in-process; semantic route had NO model during this replay "
                             "(refusing client injected); latency includes geometry, eligibility, gates, "
                             "verification and receipt construction")
    results["arm_provenance"] = {
        "schema": "cortex-arm-provenance/0.2",
        "replayed_arms": replayed,
        "transcript_sha256": "sha256:" + hashlib.sha256(Path(replies_path).read_bytes()).hexdigest(),
        "prompts_requested": len(client.requests), "prompts_served": len(client.calls),
        "prompts_missing": len(client.misses),
        "semantic_route": semantic_route,
        "declared_by_operator": {k: v for k, v in prov.items() if k != "semantic_transcript"},
    }
    disclosure = dict(results.get("resource_disclosure", {}))
    for arm in replayed:
        disclosure[arm] = (f"REPLAYED from a transcript: {prov['model']}; {prov['invocation']}; "
                           f"tool use: {prov['tool_use']}; the harness's local-model disclosure does not apply")
    if "routed_seed" in arm_names:
        disclosure["routed_seed"] = routed_disclosure
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
    ap_ = results["arm_provenance"]
    print(json.dumps({"partition": args.partition, "arms": brief, "exit": results["exit"],
                      "prompts_requested": ap_["prompts_requested"], "prompts_served": ap_["prompts_served"],
                      "prompts_missing": ap_["prompts_missing"], "semantic_route": ap_["semantic_route"]},
                     indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
