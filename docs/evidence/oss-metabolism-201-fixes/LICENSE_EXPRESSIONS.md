# License expression semantics: fixes to #201 (SPDX-1 to SPDX-7)

Offered to #201's owner as commits on `claude/oss-201-fix-licensing`, a child of #201's head `a1d2abfb`. The
active policies do not change: `ACTIVE_BINARY_POLICY` and `ACTIVE_FOUNDER_ATTACH_POLICY` stay `"P0"`. This is not a
legal review, and it claims no legal certainty.

## Founder intent

- **Directive of 2026-10-22, re-issued 2026-10-30:** finish #201's open-source metabolism, repair its defects.
  Section VII lists the expression semantics this record covers.
- **Rules this work keeps:** an unknown license is never cleared automatically. A restrictive term is never hidden
  by an unknown one beside it. AGPL is open source with conditions, not illegal. A founder signature never creates
  rights a license withholds. `packaging.licenses` stays the SPDX parser; no custom SPDX engine is added.

## What the assessor answers

Can this exact component, at this version and in this use (local subprocess, linked library, network service,
redistribution), perform its function under GREG's operating model? It returns a structured verdict, not a legal
opinion:

- `class`, `verdict` and `reason`, as before;
- `restrictive`: the known network-copyleft or not-open terms that bind. They are listed even when an unknown term
  makes the class "unclassified";
- `categories`: `open_source`, `source_available` (BUSL, SSPL, Elastic, Commons Clause, PolyForm),
  `restricted_use` (non-commercial, field of use, proprietary, non-free) or `unclassified`;
- `uncertainty`: what GREG did not read. This covers unclassified identifiers, declarations that disagree and,
  for binaries, the assumption that every DEP-5 Files stanza reaches the binary;
- from `qualify_use`, the elected `terms` and their obligations, the `not_elected` alternatives and `limits`.

## Semantics

One small parser (`greg.licensing._parse`) reads both SPDX expressions (after `packaging.licenses` canonicalizes
them) and DEP-5 License short-name fields into one tree. The evaluators are `_held_eval` for the class and the P0
hold, and `_use_eval` for the use verdict.

- **AND:** every term applies. The class is the worst; the obligations are all of them. A known network-copyleft
  or not-open term holds whatever else is unknown.
- **OR:** GREG relies on one whole alternative. For the class, the best alternative is chosen (unknown ranks worst)
  and, on a tie, one with no known restriction. For the use verdict, it is the alternative that best permits the
  use. Terms and obligations never mix across alternatives; `qualify_use` names the elected terms, and a D-LIC-1
  clearance records them.
- **WITH:** an SPDX exception (a permission) keeps the base class, and a linking exception lowers strong copyleft
  to weak. In DEP-5, a `with` addition that is not an exception, or that names a restrictive license, is
  classified, and the stricter class applies.
- **Precedence:** WITH binds tightest, then AND, then OR. In DEP-5, `, and` and `, or` bind loosest, and a bare
  comma lists licenses that all apply. Parentheses group in both syntaxes.
- **Variants:** `-only`, `-or-later` and `+` keep the family's class. CC NC/ND at any version, every AGPL version,
  SSPL, BUSL, Elastic, PolyForm and Commons Clause are classified as families. A family only ever makes an unknown
  name stricter. Bare `BSL` stays Boost, not Business Source.
- **Unknowns:** a `LicenseRef-*` or an unlisted identifier is unclassified, is named in `uncertainty` and never
  clears. An unparseable expression is unclassified, and every restrictive name in it still counts.
- **Declarations side by side:** classifiers and the legacy License field are read beside a License-Expression.
  - A stricter classifier, a restrictive one, or one naming a class absent from the expression counts.
  - A classifier that names an alternative of the expression agrees with it.
  - A License field that is valid SPDX but unclassifiable counts as unknown. Free text that GREG does not
    recognise stays informational, as #201 designed.
  - A less strict declaration is recorded as a disagreement.
- **Riders:** restrictive wording in a short declaration counts: SSPL, BUSL/BSL 1.1, ELv2, CC BY-NC, AGPL and
  Affero spellings, Commons Clause and non-commercial. An inclusive "commercial and non-commercial" phrase is masked
  first.
- **DEP-5 coverage:**
  - each Files stanza is a term carrying its `files` patterns and its `stanza`;
  - a multi-line Files list is joined;
  - a second License line in one paragraph is kept;
  - a Files line inside a paragraph starts a new stanza;
  - a Files stanza without a License is unclassified rather than skipped;
  - a stand-alone License paragraph still applies to nothing.

## Findings, re-verified at `a1d2abfb`

Every finding reproduced exactly as the review states. The skeptics' notes also hold: SPDX-1, SPDX-5 and SPDX-6
need inputs that no file on this host contains (latent), and SPDX-7 fails closed. All seven are fixed.

| Finding | Reproduced at `a1d2abf` | Fix | Tests that fail at `a1d2abf` |
| --- | --- | --- | --- |
| SPDX-1 | `Apache-2.0 with Commons-Clause` → permissive, nothing held | `_atom`: a non-exception or restrictive DEP-5 addition is classified | 7 parametrized cases (including one an unknown base would hide), plus the P0 attach test |
| SPDX-2 | `non-free and custom` → unclassified, nothing held | `_held_eval`: AND holds on any known restriction; parentheses parse | 7 cases, plus the P0 attach test |
| SPDX-3 | `License-Expression: MIT` plus a Proprietary classifier → CLEARED | `declared`: classifiers are read beside the expression | 3 cases, plus the disagreement record |
| SPDX-4 | Commons Clause, SSPL, CC BY-NC, ELv2, BSL 1.1, AGPLv3+ and LicenseRef beside a classifier → CLEARED | normalized `RIDERS`; an SPDX field GREG cannot classify counts | 11 cases |
| SPDX-5 | `CC-BY-NC-3.0`, `AGPL-1.0` → unclassified | `_lookup`: restrictive wording in an unlisted name classifies it (it only ever raises) | 7 cases |
| SPDX-6 | a second `License:` line overwrote the first | `_dep5_stanzas` | 1 test (two forms) |
| SPDX-7 | "free for commercial and non-commercial use" → not open | `INCLUSIVE` mask | 3 cases |

Section VII semantics added by the same work: conjunctive AND obligations; OR without mixed terms; OR usable when
one alternative is usable in context (5 use cases); a D-LIC-1 clearance needs no permission evidence for a
not-open alternative GREG does not take, but still needs it when every alternative is not open; precedence and
variants (8 cases); unknowns named; categories (8 cases); DEP-5 file coverage; and a structured use verdict.

**Independent oracle:** `test_the_evaluator_matches_an_independent_dnf_expansion` covers 1,750 expressions: three
atoms in seven shapes, in both syntaxes. The test expands its own tree into disjunctive normal form, sharing no
code with the parser or the evaluator. It checks four things:

- the class equals the min-max over conjunctions;
- a declaration clears exactly when one conjunction is fully cleared, so an unknown never clears;
- a restriction present in every conjunction is always reported;
- the elected terms form one conjunction.

**Test file:** `tests/unit/test_greg_license_expressions.py`, 1,835 tests. Run against `a1d2abf`'s
`greg/licensing.py`, 1,810 fail and 25 pass (`license-expressions-fail-before.txt`, beside this record). The 25 that
pass are cases with no defect at `a1d2abf`, kept as non-regression pins. Of the 1,810 failures:

- 60 named cases, each listed in that file with its assertion;
- the 1,750 oracle cases. They fail because `a1d2abf` has no `restrictive` field; the class check alone fails on
  every parenthesised DEP-5 case.

## Measured effect on real declarations (this container, Ubuntu 24.04)

| Population | Before (`a1d2abf`) to after |
| --- | --- |
| 65 distributions in the test virtualenv and 86 in the system Python | 0 verdict or class changes |
| 708 executables in `/usr/bin`, through `system_binary` | 0 verdict or hold changes |
| 834 DEP-5 copyright files in `/usr/share/doc` | 1 class change: `libetonyek-0.1-1` declares `License: MPL 2.0`, which now normalizes to `mpl-2.0`, so it moves from unclassified to weak copyleft. 0 hold changes |

The fixes close defect classes that real metadata on this host does not trigger today, and they cost no
regression. The single change is a spelling normalization of a known name, not an unknown turned into a
clearance.

## Mutants

Each new safeguard has a mutant in `scripts/ci/check_cortex_mutants.py` (open-source metabolism group, whose test
list now starts with `test_greg_license_expressions.py`). The five entries whose code moved were re-pointed at the
equivalent new code; 17 entries are new.

- **First run:** every `greg/licensing.py` mutant in the group (42) was run with the gate's own `_run_one` against
  the group's tests. 40 were caught; 2 survived:
  - "restrictive license families are unclassified at other versions": the family table was redundant with the
    rider patterns already applied to unlisted names. The table was removed, and the mutant now removes the
    patterns from the name lookup.
  - "a second License line in one DEP-5 paragraph overwrites the first": the test put the restrictive line last,
    where an overwrite keeps it. The test now puts it first and checks both terms.
- **Rerun:** both caught. The full rerun of all 42 on the final tree is recorded in the commit that adds
  `BINARY_LICENSE_POLICY.md`.

## Limits

- Only what a package declares about itself is read. A false declaration, or a rider inside a full license
  text, is not detected.
- DEP-5 assumes every Files stanza reaches the binary. GREG cannot tell which source files a binary was built
  from, so this side is conservative.
- An exception name containing the word `and` or `or` splits into two names. That is conservative: the extra name
  is unknown.
- Source-available and restricted-use terms stay `incompatible` in the use verdict. The category changes the
  reason and the evidence a D-LIC-1 clearance needs, not the verdict.
- Under P4c (a draft, not active), a card qualified before these trees existed is requalified once: its terms now
  carry trees, so the assessment digest differs.
