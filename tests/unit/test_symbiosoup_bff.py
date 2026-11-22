"""SymbioSoup Stage A: the fast kernel agrees with the specification interpreter, and the soup is deterministic
and consequence-inert."""
from __future__ import annotations

import random

import pytest

pytest.importorskip("numpy")

from developmental.symbiosoup import soup, spec  # noqa: E402


def test_splitmix_matches_cubff_reference_values():
    # SplitMix64 is fixed by CuBFF's common_language.h; both implementations must agree.
    for x in (0, 1, 5, 2**63 + 11):
        assert soup.lib().splitmix64(x) == spec.splitmix64(x)
    assert spec.splitmix64(0) == 0xE220A8397B1DCDAF


@pytest.mark.parametrize("program, expected_ops", [
    (b"", 0),                              # an all-zero tape: every byte is a no-op
    (b"+++", 3),
])
def test_hand_written_programs(program, expected_ops):
    tape = bytearray(program + bytes(128 - len(program)))
    ops = spec.evaluate(tape)
    assert ops == expected_ops
    out, fast = soup.evaluate(bytes(program + bytes(128 - len(program))))
    assert (bytes(tape), ops) == (out, fast)


def test_a_copy_loop_copies_its_own_bytes_into_the_partner():
    # '[' on a zero head skips to the matching ']'; '.' copies head0 -> head1, '}' and '>' advance the heads.
    program = b"[.>}]"
    tape = bytearray(b"x" + program + bytes(128 - len(program) - 1))
    tape[0] = ord("x")
    out, _ = soup.evaluate(bytes(tape))
    assert out == bytes(spec_run(tape))


def spec_run(tape):
    t = bytearray(tape)
    spec.evaluate(t)
    return t


def test_the_fast_kernel_matches_the_specification_on_random_tapes():
    rng = random.Random(20261122)
    alphabet = b"[]+-.,<>{}\x00\x01xyz"
    for n in range(3000):
        tape = bytearray(rng.getrandbits(8) for _ in range(128)) if n % 3 == 0 else \
            bytearray(rng.choice(alphabet) for _ in range(128))
        expected = bytearray(tape)
        ops = spec.evaluate(expected)
        assert soup.evaluate(bytes(tape)) == (bytes(expected), ops), n


def test_the_soup_is_deterministic_and_seed_dependent():
    a, b, c = soup.Soup(seed=3, programs=512), soup.Soup(seed=3, programs=512), soup.Soup(seed=4, programs=512)
    for s in (a, b, c):
        s.step(16)
    assert a.soup.tobytes() == b.soup.tobytes() != c.soup.tobytes()


def test_metrics_follow_cubff_definitions():
    rng = random.Random(1)
    random_bytes = bytes(rng.getrandbits(8) for _ in range(1 << 16))
    m = soup.metrics(random_bytes)
    assert 7.9 < m["h0"] <= 8.0 and abs(m["higher_entropy"]) < 0.2
    m = soup.metrics(b"[.>}]" * 13000)
    assert m["higher_entropy"] > 1.0                      # structure compresses


def test_the_lab_is_not_wired_to_greg():
    import pathlib
    root = pathlib.Path(soup.__file__).parents[2]
    for path in (root / "greg").rglob("*.py"):
        assert "symbiosoup" not in path.read_text(), path
