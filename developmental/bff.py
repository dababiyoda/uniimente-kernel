"""A byte-exact Python reference of CuBFF's ``bff_noheads`` soup (Stage A of the founder's 2026-11-22 research input).

Founder input, 2026-11-22: two research reports attached to the session, "UNIIMENTE Artificial Egregore: Technical
Research Report on a Self-Constructing Symbiogenetic Computational Substrate" (docs/intent/sources/
SYMBIOSOUP-RESEARCH-REPORT-2026-11-22-source.md) and "Engineering an Emergent Alien Intelligence" (GEM-MIND-
SPECIFICATION-2026-11-22-source.md). Both put the same first step first: reproduce the canonical phenomenon and build
a trusted measurement kernel before inventing anything. This module is that kernel's reference half.

What it reproduces, read from the CuBFF source at commit f212e849027c98fcf4b242eccfb5fed435223e23 (Apache-2.0,
https://github.com/paradigms-of-intelligence/cubff; ``bff.inc.h``, ``bff_noheads.cu``, ``common_language.h``):

* the 10-instruction BFF interpreter over one 128-byte tape (two 64-byte programs); both heads start at 128 and are
  masked to 0..127 before every step; ``[`` and ``]`` test the byte under head 0 for zero; an unmatched bracket ends
  the run; every byte, comment or not, spends one of the 8192 steps, and the returned count excludes comments;
* CuBFF's counter-based randomness (SplitMix64): program initialisation, per-byte mutation at 2^18 / 2^30 = 2^-12
  applied to the concatenated tape before it runs, and the per-epoch Fisher-Yates pairing shuffle;
* ``CheckSelfRep``: 13 noise partners, 4 extra generations, a byte counts when more than a quarter of the trials agree
  on it, and the score is the smaller of the two halves' counts (CuBFF calls a program self-replicating at 5).

What it is not. It is a deliberately slow specification interpreter, not CuBFF: it has not yet been differentially
tested against the CuBFF binary (building and running that binary in this session was not permitted), and pure Python
runs a soup of thousands of programs, not CuBFF's 131,072. The compression measure uses ``lzma`` because the Python
``brotli`` module is not installed here; its "higher-order entropy" is therefore not comparable to the paper's.
Nothing here is a production capability. It is consequence-inert: evolved bytes are data to the host, never code,
paths, commands or messages (the reports' non-negotiable containment rule).
"""
from __future__ import annotations

import hashlib
import lzma
import math
from dataclasses import dataclass, field

MASK64 = (1 << 64) - 1
SINGLE = 64                      # kSingleTapeSize
TAPE = 2 * SINGLE
STEPS = 8 * 1024
MUTATION_PROB = 1 << 18          # denominator 1 << 30
SELFREP_THRESHOLD = 5            # kSelfrepThreshold
SELFREP_ITERS, SELFREP_GENS = 13, 4
SOURCE = {"repository": "https://github.com/paradigms-of-intelligence/cubff",
          "commit": "f212e849027c98fcf4b242eccfb5fed435223e23", "license": "Apache-2.0",
          "files": ["bff.inc.h", "bff_noheads.cu", "common_language.h", "common.h"]}

LOOP_START, LOOP_END = ord("["), ord("]")
OPS = frozenset(b"[]+-.,<>{}")


def splitmix64(seed: int) -> int:
    z = (seed + 0x9E3779B97F4A7C15) & MASK64
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return z ^ (z >> 31)


def evaluate(tape: bytearray, steps: int = STEPS) -> int:
    """Run one 128-byte tape in place under bff_noheads semantics; return the non-comment operations executed."""
    if len(tape) != TAPE:
        raise ValueError("a BFF interaction tape is exactly 128 bytes")
    pc, h0, h1, skipped, i = 0, TAPE, TAPE, 0, 0
    while i < steps:
        h0 &= TAPE - 1
        h1 &= TAPE - 1
        c = tape[pc]
        if c == ord("<"):
            h0 -= 1
        elif c == ord(">"):
            h0 += 1
        elif c == ord("{"):
            h1 -= 1
        elif c == ord("}"):
            h1 += 1
        elif c == ord("+"):
            tape[h0] = (tape[h0] + 1) & 0xFF
        elif c == ord("-"):
            tape[h0] = (tape[h0] - 1) & 0xFF
        elif c == ord("."):
            tape[h1] = tape[h0]
        elif c == ord(","):
            tape[h0] = tape[h1]
        elif c == LOOP_START:
            if tape[h0] == 0:
                depth, pc = 1, pc + 1
                while pc < TAPE and depth > 0:
                    if tape[pc] == LOOP_END:
                        depth -= 1
                    if tape[pc] == LOOP_START:
                        depth += 1
                    pc += 1
                pc -= 1
                if depth != 0:
                    pc = TAPE
        elif c == LOOP_END:
            if tape[h0] != 0:
                depth, pc = 1, pc - 1
                while pc >= 0 and depth > 0:
                    if tape[pc] == LOOP_END:
                        depth += 1
                    if tape[pc] == LOOP_START:
                        depth -= 1
                    pc -= 1
                pc += 1
                if depth != 0:
                    pc = -1
        else:
            skipped += 1
        if pc < 0:
            i += 1
            break
        pc += 1
        if pc >= TAPE:
            i += 1
            break
        i += 1
    return i - skipped


@dataclass
class Soup:
    """CuBFF's well-mixed soup: ``n`` programs of 64 bytes, epochs of n/2 pair interactions."""
    n: int
    seed: int = 0
    mutation_prob: int = MUTATION_PROB
    programs: bytearray = field(init=False)
    epoch: int = field(init=False, default=0)
    ops: int = field(init=False, default=0)

    def __post_init__(self):
        if self.n < 2 or self.n % 2:
            raise ValueError("an even number of programs, at least two")
        s0 = self.stream(0)
        self.programs = bytearray(splitmix64((SINGLE * self.n * s0 + SINGLE * i + j) & MASK64) % 256
                                  for i in range(self.n) for j in range(SINGLE))

    def stream(self, x: int) -> int:
        """CuBFF's ``seed(x)``: SplitMix64(SplitMix64(params.seed) ^ SplitMix64(x))."""
        return splitmix64(splitmix64(self.seed) ^ splitmix64(x & MASK64))

    def pairing(self) -> list[int]:
        order, length = list(range(self.n)), self.n
        for i in range(length - 1, -1, -1):
            j = splitmix64(self.stream(self.epoch * length + i)) % (i + 1)
            order[i], order[j] = order[j], order[i]
        return order

    def step(self) -> int:
        """One epoch: shuffle into pairs, mutate each concatenated tape, run it, write both halves back."""
        order, seed_e, ops, mutations = self.pairing(), self.stream(self.epoch), 0, 0
        for index in range(self.n // 2):
            p1, p2 = order[2 * index], order[2 * index + 1]
            tape = bytearray(self.programs[p1 * SINGLE:(p1 + 1) * SINGLE] + self.programs[p2 * SINGLE:(p2 + 1) * SINGLE])
            for i in range(TAPE):
                rng = splitmix64(((self.n * seed_e + index) * TAPE + i) & MASK64)
                if ((rng >> 8) & ((1 << 30) - 1)) < self.mutation_prob:
                    tape[i] = rng & 0xFF
                    mutations += 1
            ops += evaluate(tape)
            self.programs[p1 * SINGLE:(p1 + 1) * SINGLE] = tape[:SINGLE]
            self.programs[p2 * SINGLE:(p2 + 1) * SINGLE] = tape[SINGLE:]
        self.ops += ops
        self.epoch += 1
        return mutations

    def program(self, i: int) -> bytes:
        return bytes(self.programs[i * SINGLE:(i + 1) * SINGLE])

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(self.programs).hexdigest()


def selfrep_score(program: bytes, *, seed: int = 0, n: int = 1, index: int = 0) -> int:
    """CuBFF's CheckSelfRep for one program: bytes stably reproduced in both halves over noise partners."""
    if len(program) != SINGLE:
        raise ValueError("a program is 64 bytes")
    local = splitmix64((n * seed + index) & MASK64)
    tapes = []
    for it in range(SELFREP_ITERS):
        noise = bytes(splitmix64(local ^ splitmix64((it + 1) * SINGLE + j)) % 256 for j in range(SINGLE))
        tape = bytearray(program + noise)
        evaluate(tape)
        for _ in range(SELFREP_GENS):
            tape[:SINGLE], tape[SINGLE:] = tape[SINGLE:], noise
            evaluate(tape)
        tapes.append(tape)
    res = [0, 0]
    for i in range(TAPE):
        for a in range(SELFREP_ITERS):
            if i < SINGLE and tapes[a][i] != program[i]:
                continue
            count = 1 + sum(tapes[a][i] == tapes[b][i] for b in range(a + 1, SELFREP_ITERS))
            if count > SELFREP_ITERS // 4:
                res[i // SINGLE] += 1
                break
    return min(res)


def entropy_measures(data: bytes) -> dict:
    """Byte-level Shannon entropy, a compressed size per byte (lzma, not CuBFF's Brotli) and their difference."""
    counts = [0] * 256
    for b in data:
        counts[b] += 1
    h0 = -sum(c / len(data) * math.log2(c / len(data)) for c in counts if c)
    bpb = len(lzma.compress(data, preset=6)) * 8.0 / len(data)
    return {"shannon_bits_per_byte": h0, "compressed_bits_per_byte": bpb, "higher_order_entropy": h0 - bpb,
            "compressor": "lzma preset 6 (stand-in; CuBFF uses Brotli quality 2, window 24, so values differ)"}


def op_fraction(data: bytes) -> float:
    return sum(b in OPS for b in data) / len(data)


def random_walk(start: bytes, mutations: int, *, seed: int, check_every: int = 1) -> dict:
    """The 2026 critique's counterexperiment arm: mutate one program alone, one random byte at a time, and test it.

    Same mutation physics as the soup (SplitMix64 bytes), no interaction. Returns the first mutation count at which
    the program scores as a self-replicator, or None."""
    program, best = bytearray(start), 0
    for m in range(1, mutations + 1):
        rng = splitmix64(splitmix64(seed) ^ splitmix64(m))
        program[(rng >> 8) % SINGLE] = rng & 0xFF
        if m % check_every == 0:
            score = selfrep_score(bytes(program), seed=seed)
            best = max(best, score)
            if score >= SELFREP_THRESHOLD:
                return {"found_at_mutation": m, "best_score": score, "program": bytes(program).hex()}
    return {"found_at_mutation": None, "best_score": best}
