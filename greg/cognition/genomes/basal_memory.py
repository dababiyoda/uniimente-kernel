"""Layer 1 basal intelligence: associative memory (content-addressable recall by a Hebbian Hopfield network).

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.json``, ``L1.eval.associative_networks``)
lists "evaluate associative networks" as ABSENT. Effect, not metaphor: given a set of stored binary patterns and a
corrupted cue, return the stored pattern the cue came from. The mechanism evaluated is the classical associative
network (Hopfield 1982): Hebbian outer-product weights with a zero diagonal, and asynchronous threshold updates, each
unit reading only its weighted inputs, until no unit wants to flip. The network settles in an energy minimum; when
that minimum is one of the stored patterns the genome answers with it, and when it is a spurious mixture state the
genome answers UNKNOWN rather than presenting a state nobody stored.

Honest expectation, stated before any held-out run: exact nearest neighbour by Hamming distance over the stored
patterns is the Bayes-optimal decoder for independent bit flips and a uniform prior over patterns, so no associative
network can be more accurate than it on this geometry; and because each request carries its patterns, the network's
weight matrix (N x N, built in O(P N^2)) is no cheaper than the O(P N) nearest-neighbour scan either. The evaluation
measures how far below that ceiling the associative mechanism falls (load beyond ~0.14 N, correlated patterns,
heavy corruption), which is what "evaluate associative networks" asks; a memory-bound or streaming niche, where the
weights would be built once and the patterns discarded, is not this request contract and is not claimed.

* ``basal_hopfield`` (``associative_recall``): verified by an independent replay: every recorded flip, from the cue,
  must strictly lower the network energy (the unit's local field, recomputed from the patterns without the weight
  matrix, disagrees with its state), the end state must be the claimed one and a fixed point, and the claimed
  memory index must be the stored pattern equal to it.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 only.
"""
from __future__ import annotations

import hashlib
import json
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.json (L1.eval.associative_networks ABSENT)")
AM_MAX_BITS, AM_MAX_PATTERNS = 512, 256
AM_MAX_SWEEPS = 50


def _bits(s, n=None, name="pattern"):
    if not isinstance(s, str) or not s or set(s) - {"0", "1"} or (n is not None and len(s) != n):
        raise GenomeError(f"{name}: a string of '0'/'1' of one common length")
    return [1 if ch == "1" else -1 for ch in s]


def _input(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    stored, cue = data.get("stored_patterns"), data.get("cue")
    if not isinstance(stored, list) or not 1 <= len(stored) <= AM_MAX_PATTERNS:
        raise GenomeError(f"stored_patterns: 1-{AM_MAX_PATTERNS} binary strings")
    n = len(stored[0]) if isinstance(stored[0], str) else 0
    if not 8 <= n <= AM_MAX_BITS:
        raise GenomeError(f"patterns: 8-{AM_MAX_BITS} bits")
    patterns = [_bits(s, n) for s in stored]
    return patterns, _bits(cue, n, name="cue")


def _string(state):
    return "".join("1" if v > 0 else "0" for v in state)


def _matched(patterns, state):
    for i, p in enumerate(patterns):
        if p == list(state):
            return i
    return -1


def _order_seed(data):
    return int(hashlib.sha256(("hopfield:" + json.dumps(data, sort_keys=True)).encode()).hexdigest()[:16], 16)


def hopfield_solve(data, budget):
    import numpy as np
    patterns, cue = _input(data)
    x = np.array(patterns, dtype=np.int64)                  # P x N
    w = x.T @ x                                              # Hebbian outer products (integer; 1/N dropped)
    np.fill_diagonal(w, 0)
    s = np.array(cue, dtype=np.int64)
    h = w @ s
    rng = random.Random(_order_seed(data))
    n = len(cue)
    flips, sweeps, settled = [], 0, False
    while sweeps < AM_MAX_SWEEPS:
        sweeps += 1
        order = list(range(n))
        rng.shuffle(order)
        changed = False
        for i in order:
            if s[i] * h[i] < 0:                              # the unit's field disagrees with its state: flip
                s[i] = -s[i]
                h += 2 * s[i] * w[:, i]
                flips.append(i)
                changed = True
        if not changed:
            settled = True
            break
    if not settled:
        return answer(None, {"reason": "not settled", "sweeps": sweeps}, status="UNKNOWN",
                      missing=[f"the network did not settle within {AM_MAX_SWEEPS} sweeps"])
    state = [int(v) for v in s]
    index = _matched(patterns, state)
    cert = {"rule": "Hebbian outer products, zero diagonal, asynchronous sign updates in a seeded random order",
            "flips": flips, "sweeps": sweeps}
    if index < 0:
        return answer(None, {**cert, "reason": "spurious state", "settled_state": _string(state)},
                      status="UNKNOWN", missing=["the network settled in a state that is not a stored pattern "
                                                 "(a spurious mixture); no memory is recalled"])
    return answer({"recalled": _string(state), "memory_index": index}, cert)


def hopfield_verify(data, output, certificate):
    patterns, cue = _input(data)
    n = len(cue)
    if (not isinstance(output, dict) or set(output) != {"recalled", "memory_index"}
            or not isinstance(output["recalled"], str) or len(output["recalled"]) != n
            or set(output["recalled"]) - {"0", "1"} or type(output["memory_index"]) is not int):
        return {"output_shape": False}
    flips = certificate.get("flips") if isinstance(certificate, dict) else None
    if not isinstance(flips, list) or not all(type(i) is int and 0 <= i < n for i in flips):
        return {"output_shape": True, "flip_trace_well_formed": False}
    import numpy as np
    x = np.array(patterns, dtype=np.int64)
    s = np.array(cue, dtype=np.int64)
    overlaps = x @ s                                         # xi_mu . s, updated per flip
    descends = True
    for i in flips:
        field = int(x[:, i] @ overlaps) - len(patterns) * int(s[i])
        if s[i] * field >= 0:
            descends = False
            break
        overlaps -= 2 * s[i] * x[:, i]
        s[i] = -s[i]
    state = [int(v) for v in s]
    claimed = _bits(output["recalled"], n, name="recalled")
    fields = x.T @ (x @ s) - len(patterns) * s             # every unit's field from the patterns, no weights
    stable = descends and bool(np.all(s * fields >= 0))
    index = output["memory_index"]
    return {"output_shape": True, "flip_trace_well_formed": True, "every_flip_lowers_the_energy": descends,
            "trace_ends_at_the_recalled_state": descends and state == claimed,
            "recalled_state_is_a_fixed_point": stable,
            "memory_index_names_the_recalled_pattern": 0 <= index < len(patterns) and patterns[index] == claimed}


def hopfield_score(data, truth, output):
    """Quality: fraction of bits equal to the true source pattern. Correct only for an exact recall of it; abstaining
    keeps the cue's agreement (nothing recalled, nothing claimed)."""
    patterns, cue = _input(data)
    source = patterns[truth["source"]]
    n = len(cue)
    if output is None:
        return {"quality": sum(a == b for a, b in zip(cue, source)) / n, "category": "abstain"}
    try:
        recalled = _bits(output["recalled"], n, name="recalled")
    except (GenomeError, KeyError, TypeError):
        return {"quality": 0.0, "category": "wrong"}
    agree = sum(a == b for a, b in zip(recalled, source)) / n
    return {"quality": agree, "category": "correct" if recalled == source else "wrong"}


def hopfield_no_recall(data):
    """Baseline: no memory at all; the cue is returned as the recalled pattern."""
    patterns, cue = _input(data)
    return {"recalled": _string(cue), "memory_index": _matched(patterns, cue)}


def hopfield_nearest(data):
    """Competitor: exact nearest neighbour by Hamming distance over every stored pattern (NumPy; ties to the lowest
    index). Bayes-optimal for independent flips and a uniform prior, so it is the accuracy ceiling here."""
    import numpy as np
    patterns, cue = _input(data)
    overlaps = np.array(patterns, dtype=np.int64) @ np.array(cue, dtype=np.int64)
    index = int(np.argmax(overlaps))
    return {"recalled": _string(patterns[index]), "memory_index": index}


def hopfield_instance(seed):
    r = random.Random(f"genome:basal_hopfield:{seed}")
    n = r.choice((64, 96, 128, 192, 256))
    load = r.uniform(0.02, 0.25)
    count = max(2, round(load * n))
    bias = r.choice((0.0, 0.0, 0.1, 0.2))                    # P(bit = 1) = 0.5 + bias: correlated patterns
    flip = r.uniform(0.05, 0.30)
    patterns = []
    while len(patterns) < count:
        p = "".join("1" if r.random() < 0.5 + bias else "0" for _ in range(n))
        if p not in patterns:
            patterns.append(p)
    source = r.randrange(count)
    cue = list(patterns[source])
    for i in r.sample(range(n), max(1, round(flip * n))):
        cue[i] = "1" if cue[i] == "0" else "0"
    data = {"stored_patterns": patterns, "cue": "".join(cue)}
    return data, {"source": source, "load": count / n, "bias": bias, "flip": flip}


def hopfield_subregion(data):
    """Load against the Hebbian capacity (~0.138 N for random patterns) and pattern bias, from the data alone."""
    stored = data["stored_patterns"]
    n = len(stored[0])
    ones = sum(s.count("1") for s in stored) / (n * len(stored))
    return ("low_load" if len(stored) / n < 0.138 else "over_capacity") + ("_biased" if ones > 0.55 else "_random")


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="basal.memory.hopfield_hebbian", version="1.0.0", family="basal_hopfield", layer=1,
            operation="associative_recall", epistemic_class="estimate",
            subgeometry="content-addressable recall of a stored binary pattern from a cue corrupted by bit flips",
            source_provenance="Hopfield (1982) neural networks and emergent collective computation; Hebb (1949); "
                              "Amit, Gutfreund and Sompolinsky (1985) storage capacity ~0.138 N",
            native_representation="stored_patterns: binary strings of one length N; cue: a binary string of length N",
            required_inputs=("stored_patterns", "cue"),
            output_contract={"recalled": "the stored pattern the network settled in (binary string)",
                             "memory_index": "its index in stored_patterns"},
            algorithm_or_runtime="integer Hebbian weights W = X^T X with zero diagonal (NumPy), asynchronous sign "
                                 "updates in a seeded random order with incremental local fields, until a sweep "
                                 "flips nothing (at most 50 sweeps)",
            parameters={"max_sweeps": AM_MAX_SWEEPS},
            memory_model="the weight matrix built from the request's patterns; nothing persists across requests",
            learning_rule="Hebbian outer-product rule (one shot, no iteration)",
            composition_inputs=("stored binary codes", "a noisy or partial probe"),
            composition_outputs=("the recalled stored code", "its index"),
            evidence_type="heuristic_trace",
            verification_method="independent replay of the flip trace from the cue with local fields recomputed from "
                                "the patterns (no weight matrix): every flip strictly lowers the energy, the end state "
                                "is the recalled one and a fixed point, and the index names the equal stored pattern",
            confidence_semantics="the recalled pattern is a stored pattern and an energy minimum reached from the "
                                 "cue; it is not certified to be the nearest stored pattern or the cue's source",
            resource_profile="O(P N^2) to build the weights, O(N) per update; N <= 512, P <= 256",
            latency_profile="milliseconds",
            known_strengths=("purely local updates: each unit reads only its weighted inputs",
                             "abstains on spurious mixture states instead of presenting them",
                             "corrects moderate corruption at low load"),
            known_failure_modes=("capacity: above ~0.138 N random patterns recall collapses into spurious states",
                                 "correlated (biased) patterns interfere: the plain Hebbian rule has no bias correction",
                                 "never more accurate than exact nearest neighbour on independent flips (the Bayes "
                                 "decoder), and not cheaper when the patterns arrive with the request",
                                 "can settle in the wrong stored pattern when the cue is heavily corrupted"),
            counterindications=("requests where exact recall matters (use nearest neighbour)",
                                "many or correlated patterns", "continuous-valued data"),
            abstention_conditions=("UNKNOWN when the network settles in a state that is not a stored pattern",
                                   "UNKNOWN when it does not settle within 50 sweeps"),
            benchmark_suite="N in {64, 96, 128, 192, 256} bits, load P/N uniform in 0.02-0.25, patterns random or "
                            "biased (P(1) = 0.6 or 0.7), cue = one stored pattern with 5-30% of bits flipped; quality "
                            "is bit agreement with the source pattern, correct only on exact recall; seeds 0-9 dev, "
                            "held-out seeds fixed by the admission freeze",
            baseline="no recall: the cue is returned as the answer",
            competitor="exact nearest neighbour by Hamming distance over every stored pattern (NumPy)",
            dependency=None, buildability="BUILDABLE_NOW", lineage=LINEAGE),
        solve=hopfield_solve, verify=hopfield_verify, instance=hopfield_instance, score=hopfield_score,
        baseline=hopfield_no_recall, competitor=hopfield_nearest, subregion=hopfield_subregion, tolerance=1e-9),
]
