"""The deliberately slow specification interpreter: CuBFF bff_noheads semantics in plain Python.

It exists only to check ``bff_ref.c`` byte for byte (the reports' differential-test gate); it is never the fast
path. Semantics: CuBFF bff.inc.h (Apache-2.0, Google LLC) at commit f212e849."""
from __future__ import annotations

MASK = (1 << 64) - 1
TAPE, PAIR, STEPS = 64, 128, 8 * 1024
OPS = {ord("["): "LS", ord("]"): "LE", ord("+"): "PL", ord("-"): "MI", ord("."): "C01", ord(","): "C10",
       ord("<"): "D0", ord(">"): "I0", ord("{"): "D1", ord("}"): "I1", 0: "NUL"}


def splitmix64(seed: int) -> int:
    z = (seed + 0x9E3779B97F4A7C15) & MASK
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31)


def kind(byte: int) -> str:
    return OPS.get(byte, "NOP")


def evaluate(tape: bytearray, steps: int = STEPS) -> int:
    """Run one 128-byte pair in place; return CuBFF's operation count (non-comment steps)."""
    h0 = h1 = PAIR
    pc = i = skipped = 0
    while i < steps:
        h0 %= PAIR
        h1 %= PAIR
        op = kind(tape[pc])
        if op == "D0":
            h0 -= 1
        elif op == "I0":
            h0 += 1
        elif op == "D1":
            h1 -= 1
        elif op == "I1":
            h1 += 1
        elif op == "PL":
            tape[h0] = (tape[h0] + 1) % 256
        elif op == "MI":
            tape[h0] = (tape[h0] - 1) % 256
        elif op == "C01":
            tape[h1] = tape[h0]
        elif op == "C10":
            tape[h0] = tape[h1]
        elif op == "LS":
            if kind(tape[h0]) == "NUL":
                depth, pc = 1, pc + 1
                while pc < PAIR and depth > 0:
                    depth += {"LE": -1, "LS": 1}.get(kind(tape[pc]), 0)
                    pc += 1
                pc -= 1
                if depth != 0:
                    pc = PAIR
        elif op == "LE":
            if kind(tape[h0]) != "NUL":
                depth, pc = 1, pc - 1
                while pc >= 0 and depth > 0:
                    depth += {"LE": 1, "LS": -1}.get(kind(tape[pc]), 0)
                    pc -= 1
                pc += 1
                if depth != 0:
                    pc = -1
        else:
            skipped += 1
        i += 1
        if pc < 0:
            break
        pc += 1
        if pc >= PAIR:
            break
    return i - skipped
