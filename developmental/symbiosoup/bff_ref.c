/* SymbioSoup Stage A: a reference implementation of the CuBFF "bff_noheads" soup.
 *
 * Semantics reimplemented from CuBFF (github.com/paradigms-of-intelligence/cubff, commit
 * f212e849027c98fcf4b242eccfb5fed435223e23; Copyright 2024-2025 Google LLC, Apache License 2.0):
 * bff.inc.h (operations, Evaluate), common_language.h (SplitMix64, InitPrograms, MutateAndRunPrograms,
 * the Fisher-Yates shuffle) and common.h (64-byte programs, mutation 2^18 / 2^30 per byte, 8192 steps).
 *
 * Consequence-inert by construction: evolved bytes are data. Nothing here reads files, opens sockets,
 * spawns processes or calls the host with program bytes; the interpreter only reads and writes its own
 * 128-byte tape.
 */
#include <stdint.h>
#include <stddef.h>

#define TAPE 64
#define PAIR 128

static inline uint64_t sm64(uint64_t s) {
  uint64_t z = s + 0x9e3779b97f4a7c15ULL;
  z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
  z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
  return z ^ (z >> 31);
}

enum { LS, LE, PL, MI, C01, C10, D0, I0, D1, I1, NUL, NOP };

static inline int kind(uint8_t c) {
  switch (c) {
    case '[': return LS; case ']': return LE; case '+': return PL; case '-': return MI;
    case '.': return C01; case ',': return C10; case '<': return D0; case '>': return I0;
    case '{': return D1; case '}': return I1; case 0: return NUL; default: return NOP;
  }
}

uint64_t splitmix64(uint64_t s) { return sm64(s); }

/* Executes one concatenated pair in place; returns executed non-comment operations (CuBFF's count). */
uint64_t bff_eval(uint8_t *tape, uint64_t steps) {
  int h0 = PAIR, h1 = PAIR, pc = 0;
  uint64_t i = 0, nskip = 0;
  for (; i < steps; i++) {
    h0 &= PAIR - 1;
    h1 &= PAIR - 1;
    switch (kind(tape[pc])) {
      case D0: h0--; break;
      case I0: h0++; break;
      case D1: h1--; break;
      case I1: h1++; break;
      case PL: tape[h0]++; break;
      case MI: tape[h0]--; break;
      case C01: tape[h1] = tape[h0]; break;
      case C10: tape[h0] = tape[h1]; break;
      case LS:
        if (kind(tape[h0]) == NUL) {
          size_t open = 1;
          pc++;
          for (; pc < PAIR && open > 0; pc++) {
            if (kind(tape[pc]) == LE) open--;
            if (kind(tape[pc]) == LS) open++;
          }
          pc--;
          if (open != 0) pc = PAIR;
        }
        break;
      case LE:
        if (kind(tape[h0]) != NUL) {
          size_t open = 1;
          pc--;
          for (; pc >= 0 && open > 0; pc--) {
            if (kind(tape[pc]) == LE) open++;
            if (kind(tape[pc]) == LS) open--;
          }
          pc++;
          if (open != 0) pc = -1;
        }
        break;
      default: nskip++;
    }
    if (pc < 0) { i++; break; }
    pc++;
    if (pc >= PAIR) { i++; break; }
  }
  return i - nskip;
}

static inline uint64_t run_seed(uint64_t base, uint64_t x) { return sm64(sm64(base) ^ sm64(x)); }

void bff_init(uint8_t *programs, uint64_t n, uint64_t base_seed) {
  uint64_t s = run_seed(base_seed, 0);
  for (uint64_t idx = 0; idx < n; idx++)
    for (uint64_t i = 0; i < TAPE; i++)
      programs[idx * TAPE + i] = (uint8_t)(sm64(TAPE * n * s + TAPE * idx + i) % 256);
}

/* Runs epochs [first, first + count); returns executed operations. Pairs are disjoint, so the parallel
 * loop is deterministic. */
uint64_t bff_epochs(uint8_t *programs, uint32_t *shuf, uint64_t n, uint64_t base_seed, uint32_t mutation_prob,
                    uint64_t first, uint64_t count) {
  uint64_t total = 0;
  for (uint64_t epoch = first; epoch < first + count; epoch++) {
    for (uint64_t i = 0; i < n; i++) shuf[i] = (uint32_t)i;
    for (uint64_t i = n; i-- > 0;) {
      uint64_t j = run_seed(base_seed, epoch * n + i) % (i + 1);
      uint32_t t = shuf[i]; shuf[i] = shuf[j]; shuf[j] = t;
    }
    uint64_t seed = run_seed(base_seed, epoch), ops = 0;
#pragma omp parallel for reduction(+ : ops) schedule(dynamic, 256)
    for (int64_t idx = 0; idx < (int64_t)(n / 2); idx++) {
      uint8_t tape[PAIR];
      uint32_t p1 = shuf[2 * idx], p2 = shuf[2 * idx + 1];
      for (int k = 0; k < TAPE; k++) {
        tape[k] = programs[(uint64_t)p1 * TAPE + k];
        tape[k + TAPE] = programs[(uint64_t)p2 * TAPE + k];
      }
      for (int k = 0; k < PAIR; k++) {
        uint64_t r = sm64((n * seed + (uint64_t)idx) * PAIR + (uint64_t)k);
        if (((r >> 8) & ((1ULL << 30) - 1)) < mutation_prob) tape[k] = (uint8_t)(r & 0xFF);
      }
      ops += bff_eval(tape, 8 * 1024);
      for (int k = 0; k < TAPE; k++) {
        programs[(uint64_t)p1 * TAPE + k] = tape[k];
        programs[(uint64_t)p2 * TAPE + k] = tape[k + TAPE];
      }
    }
    total += ops;
  }
  return total;
}
