"""SymbioSoup Stage A driver: the CuBFF bff_noheads primordial soup, measured as CuBFF measures it.

The fast kernel is ``bff_ref.c``, compiled once per source digest into a per-user cache. The kernel is checked
against ``spec.py`` (tests). Metrics follow CuBFF's callback: zeroth-order Shannon entropy over soup bytes,
Brotli quality 2 / window 24 bits per byte, and the higher-order entropy ``h0 - bpb``. Consequence-inert: no
evolved byte ever leaves the soup buffer.
"""
from __future__ import annotations

import ctypes
import hashlib
import math
import os
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "bff_ref.c"
TAPE = 64
MUTATION_PROB = 1 << 18          # CuBFF default: 2^18 / 2^30 = 2^-12 per byte per interaction
CANONICAL_PROGRAMS = 128 * 1024
CALLBACK_INTERVAL = 128


def _library() -> ctypes.CDLL:
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()[:16]
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "uniimente-symbiosoup"
    cache.mkdir(parents=True, exist_ok=True)
    lib = cache / f"bff_ref-{digest}.so"
    if not lib.exists():
        tmp = lib.with_suffix(f".{os.getpid()}.tmp")
        subprocess.run(["cc", "-O2", "-fPIC", "-shared", "-fopenmp", str(SOURCE), "-o", str(tmp)], check=True)
        tmp.replace(lib)
    dll = ctypes.CDLL(str(lib))
    u8p, u32p = ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_uint32)
    dll.bff_eval.restype = ctypes.c_uint64
    dll.bff_eval.argtypes = [u8p, ctypes.c_uint64]
    dll.splitmix64.restype = ctypes.c_uint64
    dll.splitmix64.argtypes = [ctypes.c_uint64]
    dll.bff_init.restype = None
    dll.bff_init.argtypes = [u8p, ctypes.c_uint64, ctypes.c_uint64]
    dll.bff_epochs.restype = ctypes.c_uint64
    dll.bff_epochs.argtypes = [u8p, u32p, ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint32, ctypes.c_uint64,
                               ctypes.c_uint64]
    return dll


_DLL = None


def lib() -> ctypes.CDLL:
    global _DLL
    if _DLL is None:
        _DLL = _library()
    return _DLL


def evaluate(tape: bytes, steps: int = 8 * 1024) -> tuple[bytes, int]:
    """Fast path for one pair: the tape after execution, and the operation count."""
    buf = (ctypes.c_uint8 * len(tape)).from_buffer_copy(tape)
    ops = lib().bff_eval(buf, steps)
    return bytes(buf), int(ops)


def metrics(soup: bytes) -> dict:
    import brotli
    counts = Counter(soup)
    n = len(soup)
    h0 = -sum(c / n * math.log2(c / n) for c in counts.values())
    bpb = len(brotli.compress(soup, quality=2, lgwin=24)) * 8.0 / n
    top = counts.most_common(3)
    return {"h0": round(h0, 4), "brotli_bpb": round(bpb, 4), "higher_entropy": round(h0 - bpb, 4),
            "top_bytes": [[b, round(c / n, 4)] for b, c in top]}


@dataclass
class Soup:
    seed: int
    programs: int = CANONICAL_PROGRAMS
    mutation_prob: int = MUTATION_PROB
    epoch: int = 0

    def __post_init__(self):
        if self.programs % 2:
            raise ValueError("an even number of programs")
        self.soup = np.zeros(self.programs * TAPE, dtype=np.uint8)
        self._shuf = np.zeros(self.programs, dtype=np.uint32)
        lib().bff_init(self.soup.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), self.programs, self.seed)

    def step(self, epochs: int) -> int:
        ops = lib().bff_epochs(self.soup.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
                               self._shuf.ctypes.data_as(ctypes.POINTER(ctypes.c_uint32)), self.programs, self.seed,
                               self.mutation_prob, self.epoch, epochs)
        self.epoch += epochs
        return int(ops)

    def run(self, max_epochs: int, *, interval: int = CALLBACK_INTERVAL, threshold: float = 1.0, after: int = 0,
            on_point=None) -> dict:
        """Run to ``max_epochs``; record CuBFF's metrics every ``interval`` epochs. The transition epoch is the
        first checkpoint whose higher-order entropy reaches ``threshold``; ``after`` more checkpoints are
        recorded past it, then the run stops early."""
        points, transition, remaining = [], None, None
        while self.epoch < max_epochs:
            ops = self.step(min(interval, max_epochs - self.epoch))
            point = {"epoch": self.epoch, "ops_per_pair": round(ops / (interval * self.programs / 2), 2),
                     **metrics(self.soup.tobytes())}
            points.append(point)
            if on_point:
                on_point(point)
            if transition is None and point["higher_entropy"] >= threshold:
                transition, remaining = self.epoch, after
            elif remaining is not None:
                remaining -= 1
            if remaining is not None and remaining <= 0:
                break
        return {"seed": self.seed, "programs": self.programs, "mutation_prob": self.mutation_prob,
                "max_epochs": max_epochs, "threshold": threshold, "transition_epoch": transition,
                "last_epoch": self.epoch, "points": points}
