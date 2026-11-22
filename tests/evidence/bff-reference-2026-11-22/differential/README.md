# Differential test: `developmental/bff.py` against the CuBFF binary

Date: 2026-11-22. Requested by the founder in session chat: "build CuBFF with make CUDA=0 and run the differential
test". This is consequence-inert research inside `developmental/`. Evolved bytes are data. Nothing here grants
authority.

## Result

**No mismatch was found, so `developmental/bff.py` was not changed.**

| Comparison | Compared | Identical |
| --- | ---: | ---: |
| Soup checkpoints, every byte (seeds 0 and 1, 1,024 programs, epochs 1, 65, 129, 193, 257, 321) | 12 | 12 |
| Single 128-byte tapes: final bytes and operation count | 800 | 800 |
| `CheckSelfRep` scores | 114 | 114 |

- **Tapes:**
  - 300 uniform-random tapes;
  - 300 tapes drawn from the ten instructions and the zero byte, so that loops and copies actually run;
  - 200 pairs of programs taken from the epoch-321 soups.

  Of the 800, 21 ran into the 8,192-step cap and 456 changed their tape.
- **`CheckSelfRep`:** 64 programs from the epoch-321 soups (all scored 0), and 50 programs that CuBFF scored above 0.
  The 50 were found by a search among 20,000 variants of reversed-copy loops; their scores ranged from 1 to 64, the
  maximum.

The per-row digests and inputs are in `differential.json`. `tests/unit/test_developmental_bff_differential.py`
re-checks them without the binary:

- it recomputes the first two checkpoints per seed;
- it recomputes all 800 tapes;
- it recomputes 16 of the `CheckSelfRep` scores.

Two deliberate mutants of the reference were caught against the record: a doubled mutation rate, and an operation
count off by one.

## How it was run

- **CuBFF:** https://github.com/paradigms-of-intelligence/cubff at commit
  `f212e849027c98fcf4b242eccfb5fed435223e23`, Apache-2.0. Its sources and binaries are not committed here.
- **Compiler:** g++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0. libbrotli-dev 1.1.0 was already present; no package
  was installed.
- **Build:** `make CUDA=0` in the checkout. This produces `bin/main`, compiled with `-O3 -fopenmp`.
- **Soup:**
  `bin/main --lang bff_noheads --num 1024 --seed S --max_epochs 257 --save_interval 64 --checkpoint_dir DIR --disable_output`,
  for S = 0 and 1.
- **Tapes and `CheckSelfRep`:** `harness.cc`, a 27-line harness kept in this directory.
  - It `#include`s CuBFF's unchanged `bff_noheads.cu` and calls `Bff::Evaluate(tape, 8192)` and
    `Simulation<Bff>::EvalParsedSelfrep(program, epoch, seed)`.
  - It is used because `--run` prints colour-coded glyphs rather than bytes, and the Python bindings need pybind11,
    which is not installed.
  - Build it with
    `g++ -c -std=c++17 -O3 -fopenmp -xc++ -I CUBFF harness.cc -o harness.o && g++ harness.o CUBFF/build/common.o -fopenmp -lbrotlienc -lbrotlicommon -o harness`.
- **Everything:** `python differential.py CUBFF HARNESS differential.json` runs all of the above and writes the
  record.

### How the checkpoints line up

CuBFF saves inside its print block (`common_language.h`):

- **When:** after stepping loop index `e`, when `e % 64 == 0`. The check runs every `print_interval` epochs, so the
  save interval must be a multiple of the print interval (64 by default).
- **File name:** `e.dat`.
- **Header:** `reset_index`, `num_programs` and `e + 1`, then the soup.

So `0000000064.dat` is the soup after 65 epochs, which is `Soup(1024, seed=S)` after 65 calls to `step()`.

`--max_epochs` is checked only at a print interval, so asking for 257 epochs also wrote `0000000320.dat` (321
epochs). That file was compared too.

`EvalParsedSelfrep(program, epoch, seed)` scores a single program at index 0 with the seed
`SplitMix64(SplitMix64(seed) ^ SplitMix64(epoch))`. That seed is `bff.Soup(_, seed=seed).stream(epoch)` with `n=1`
and `index=0`.

## Stage A scale run (CuBFF itself, CPU)

The report's Stage A scale was 131,072 programs, up to 16,000 epochs per seed. Seeds 0 to 7 were run one after
another on 4 CPU cores. Each run used
`bin/main --lang bff_noheads --num 131072 --seed S --max_epochs 16000 --print_interval 256 --save_interval 256 --clear_interval 2048 --eval_selfrep --stopping_selfrep_count 13108 --disable_output --log seedS.csv`.
CuBFF's own logs and wall times are in `scale-logs/`. `scale.py` summarised them into `scale.json`.

**Criterion, fixed before any seed was looked at:** at least 13,108 programs (10% of the soup) score ≥ 5 on CuBFF's
`CheckSelfRep` at a logged epoch (every 256 epochs). Higher-order entropy is recorded beside it.

| Seed | Outcome | First epoch meeting the criterion | Replicators then | Higher-order entropy, before → at |
| ---: | --- | ---: | ---: | --- |
| 0 | transition | 2,817 | 43,052 | 0.72 → 2.53 |
| 1 | none by 16,129 | — | 0 throughout | max 0.36 |
| 2 | transition | 12,033 | 129,053 | 1.19 → 4.02 |
| 3 | none by 16,129 | — | 0 throughout | max 0.38 |
| 4 | none by 16,129 | — | 0 throughout | max 0.38 |
| 5 | none by 16,129 | — | 0 throughout | max 0.37 |
| 6 | none by 16,129 | — | 0 throughout | max 0.36 |
| 7 | transition | 12,545 | 14,825 | 0.12 → 3.05 |

- **Rate:** 3 transitions in 8 finished seeds, 37.5%. The exact (Clopper–Pearson) 95% interval is 8.5% to 75.5%.
- **Against the paper:** the paper reports about 40% within 16,000 epochs, which lies inside the interval.
- **Verdict:** inconclusive. Eight seeds cannot distinguish 40% from rates anywhere between about 9% and 75%. The
  report asks for 50 to 100 seeds.

The three transitions are abrupt. Within one or two 256-epoch intervals:

- **Seed 0:** replicators went from 0 to 949 to 43,052.
- **Seed 2:** from 3 to 4,544 to 129,053.
- **Seed 7:** from 0 to 14,825.

In each, higher-order entropy rose to between 2.5 and 4. In the five seeds
without a transition, no program ever scored as a replicator and higher-order entropy stayed below 0.4.

Each seed took 5 to 23 minutes. A seed stops early once it transitions; one that never does runs all 16,000 epochs,
about 17 minutes on 4 cores. The seed-1 time includes contention with the differential test, which ran at the same
time.

Seed 7 was first started at the end of the sequential loop. That attempt was stopped at epoch 2,305, before the
loop's time limit could cut it off, and was discarded unread. Seed 7 was then rerun from epoch 0 on its own, and that
rerun is the one recorded.
