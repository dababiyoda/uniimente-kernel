# Binary license policy: measured options for founder decision D-LIC-2 (2026-10-22)

Directive of 2026-10-22, section VII, "The binary-license asymmetry". This record changes no policy. #201 keeps
its current rule: a system binary is held only on a **known** network-copyleft or not-open term, and an
unclassified one attaches as before licenses were read. Whether that rule should change is the founder's
decision. The numbers below were measured to inform it.

## Measurement

Body: this cloud container (Ubuntu userland, dpkg), 2026-10-22. Sample: every executable regular file in
`/usr/bin`, 707 binaries from 144 packages. Reproduce with
`PYTHONPATH=. python docs/open-source/binary-license-policy-2026-10-22/measure_binary_policies.py`. Raw numbers
are in `binary-license-policy-2026-10-22/measurement.json`.

**GREG's DEP-5 reader alone**

| Verdict | Binaries |
| --- | ---: |
| `UNCLASSIFIED_PRIOR_BEHAVIOUR` | 439 (62%) |
| `CLEARED_WITH_OBLIGATIONS` | 244 |
| `CLEARED` | 21 |
| no dpkg owner or no DEP-5 file | 3 |
| `FOUNDER_REVIEW` | 0 |

The unclassified share is not exotic software. It is bash, util-linux, perl (`shasum`), bzip2, autoconf and
python. Their DEP-5 files use Debian maintainers' own license names, such as `permissive`, `other`,
`ImageMagick`, `BSD-variant`, `GPL3+-with-Autoconf-Macros-exception` and `LGPL`. 36 of the 107 packages have no
DEP-5 file at all. Name tables cannot close this tail.

**With a mature text scanner.** scancode-toolkit-mini 32.5.0 (Apache-2.0; nexB/AboutCode) was run outside GREG,
in a scratch virtualenv, on the 142 copyright files present. Each license key was mapped to a class through
scancode's own license category (`docs/open-source/binary-license-policy-2026-10-22/scancode_classes.py`).

- **Coverage:** unclassified packages fall from 105 to 35, and unclassified binaries from 436 to 95. Scancode's
  "Unstated License" keys (`unknown-license-reference`, `warranty-disclaimer`, `other-permissive`) remain.
- **Independent cross-check:** a different algorithm (text matching, not name lookup) agrees with GREG's class
  on 34 of the 37 packages GREG classifies.
  - `openssl`: GREG says weak copyleft, scancode strong. A `GPL-1.0-or-later` alternative appears in its file.
  - `diffutils` and `software-properties-common`: scancode leaves them unclassified.
- **Holds:** scancode would hold `php8.3-cli` and `php8.3-dev` (2 binaries each) as not open, through a
  component it categorises "Proprietary Free" or "Commercial". This looks over-conservative and needs a human
  reading.
- **Defect found in the tool's packaging:** scancode 32.5.0 does not start with pluggy 1.7.0 ("did not find any
  'pre_scan' hooks"). It needs `pluggy<1.5`.
- **Cost:** a 126 MB wheel plus dependencies, not installed on any body. Installing it is the founder's.

## Options compared

"Held" means the binary waits for the founder's own `CAPABILITY_ATTACH`.

| Option | Held on this body | Regression risk | Legal-supply-chain risk |
| --- | ---: | --- | --- |
| P0, current: hold only known uncleared terms | 0 | none | an unread AGPL or proprietary binary attaches by itself |
| P1, fail closed on everything not cleared | 442 | high: `shasum` (a `hash.sha256` route) and most of the OS wait for the founder | lowest |
| P2, catalog allowlist, then fail closed | 441 | low for today's catalog; every new binary function needs an allowlist edit | low; the allowlist is unreviewed by construction |
| P3, scancode text classification, then fail closed on what is still unclassified | about 95 + 4 | moderate: valgrind, imagemagick, python, vim and xz-utils still wait | low; text matching, not names |
| P4, use context: hold any network-copyleft or not-open term, and for unclassified terms hold only when the binary would be exposed to a network or redistributed | 0 today; GREG's catalog binaries run with no network and are never redistributed | none | equal to P0 under GREG's current use; rises the day a binary gets network access |

## Recommendation for the founder (proposal, not decided)

**P4 now, P3 as the next acquisition.**

- **P4:** the class names already describe GREG's use (unmodified, a separate no-network process, not
  redistributed). Under that use the obligations of every open-source class are met, and only not-open terms
  matter. P0 already holds those whenever they are named. Making the use condition explicit keeps P0's zero
  regressions and states when it stops being true. A binary run with network access, or shipped with GREG,
  must then be fail-closed on unclassified terms.
- **P3:** attach scancode as a founder-installed, founder-attached `legal.assess` capability that reads
  copyright texts. That cuts the unread share by about 78% of binaries.
- **What the founder decides:**
  - (a) whether P4's use condition is the policy;
  - (b) whether to install scancode-toolkit on the body;
  - (c) whether founder attach of a held package or binary may proceed. That question is D-LIC-1, recorded
    separately.

Nothing in this record is enforced. The enforced rule is still P0.
