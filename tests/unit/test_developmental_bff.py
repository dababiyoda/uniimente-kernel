"""Stage A of the founder's 2026-11-22 research input: a trusted, byte-exact reference of CuBFF's bff_noheads soup.

Every expectation below is read from the CuBFF source (developmental/bff.py SOURCE), not from either report's prose.
"""
import pytest

from developmental import bff

REPLICATOR = b"{[<},]],}<[{"          # the 12-byte palindrome the Gemini specification cites


def padded(core, pad=b" ", offset=0):
    return (pad * offset + core + pad * bff.SINGLE)[:bff.SINGLE]


def test_splitmix64_matches_the_published_test_vector():
    assert bff.splitmix64(0) == 0xE220A8397B1DCDAF
    assert bff.splitmix64(bff.MASK64) < 1 << 64


def test_interpreter_semantics_match_cubff():
    # comments spend steps but are not counted; a tape of comments runs off the end after 128 steps
    assert bff.evaluate(bytearray(b" " * 128)) == 0
    # heads start at 0: '+' increments byte 0 (the '+' itself), '.' copies head0's byte to head1's (same cell)
    tape = bytearray(b"+" + b" " * 127)
    bff.evaluate(tape)
    assert tape[0] == ord("+") + 1
    # '<' wraps head 0 to 127; '-' then decrements the last byte
    tape = bytearray(b"<-" + b" " * 126)
    bff.evaluate(tape)
    assert tape[127] == ord(" ") - 1
    # '[' over a zero byte with no matching ']' ends the run at once
    tape = bytearray(b"[" + b" " * 126 + b"\x00")
    tape[0] = ord("[")
    t = bytearray(128)
    t[0] = ord("[")
    assert bff.evaluate(t) == 1
    # ']' over a non-zero byte with no matching '[' ends the run
    t = bytearray(b"+]" + b" " * 126)
    assert bff.evaluate(t) == 2
    # an infinite loop stops at exactly the 8192-step cap
    t = bytearray(b"+[]" + b" " * 125)
    assert bff.evaluate(t) == bff.STEPS
    with pytest.raises(ValueError):
        bff.evaluate(bytearray(64))


def test_cubffs_self_replication_rule_finds_the_cited_replicator_only_with_nonzero_padding():
    # A finding, not a premise: the palindrome copies itself fully (64 of 64 bytes, both halves) wherever it sits in a
    # program of non-zero inert bytes, and not at all among zero bytes, because zero is the loop-exit byte.
    for offset in (0, 20, 52):
        assert bff.selfrep_score(padded(REPLICATOR, b" ", offset)) == bff.SINGLE
    assert bff.selfrep_score(padded(REPLICATOR, b"\x00")) == 0
    assert bff.selfrep_score(b" " * 64) == 0 and bff.selfrep_score(bytes(64)) == 0


def test_the_soup_is_deterministic_and_counter_based():
    a, b, c = bff.Soup(32, seed=7), bff.Soup(32, seed=7), bff.Soup(32, seed=8)
    assert a.digest() == b.digest() != c.digest()
    for _ in range(3):
        a.step(), b.step()
    assert a.digest() == b.digest() and a.ops == b.ops and a.epoch == 3
    # the pairing is a permutation of every program
    assert sorted(bff.Soup(64, seed=1).pairing()) == list(range(64))
    with pytest.raises(ValueError):
        bff.Soup(3)


def test_mutation_runs_at_cubffs_rate():
    soup, mutated = bff.Soup(512, seed=3), 0
    for _ in range(6):
        mutated += soup.step()
    rate = mutated / (6 * 512 * bff.SINGLE)
    assert abs(rate - 2 ** -12) < 2 ** -12 * 0.35           # 196,608 bytes: expected 48 mutations


def test_one_seeded_replicator_persists_or_dies_out_by_chance():
    # Measured, not assumed: one copy among 63 random programs, no mutation, 30 epochs. When it runs second in a pair
    # the partner's code runs first and can overwrite it, so persistence is stochastic: over seeds 0-4 it held 26, 0,
    # 30, 0 and 24 programs. Seeds 0 and 1 are pinned; the counter-based randomness makes each run exactly repeatable.
    def survivors(seed):
        soup = bff.Soup(64, seed=seed, mutation_prob=0)
        soup.programs[:bff.SINGLE] = padded(REPLICATOR)
        for _ in range(30):
            soup.step()
        return sum(REPLICATOR in soup.program(i) for i in range(soup.n))
    assert survivors(0) == 26 and survivors(1) == 0


def test_measures_and_the_counterexperiment_arm_run():
    m = bff.entropy_measures(bytes(range(256)) * 4)
    assert m["shannon_bits_per_byte"] == pytest.approx(8.0) and "lzma" in m["compressor"]
    assert bff.op_fraction(b"[]+-.,<>{}" + b" " * 10) == 0.5
    walk = bff.random_walk(bytes(64), 20, seed=1, check_every=5)
    assert walk["found_at_mutation"] is None or walk["best_score"] >= bff.SELFREP_THRESHOLD
