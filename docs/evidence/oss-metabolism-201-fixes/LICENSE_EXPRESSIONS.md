# License expression semantics: fixes to #201 (SPDX-1 to SPDX-7)

Offered to #201's owner as commits on `claude/oss-201-fix-licensing`, a child of #201's head `a1d2abfb`. The
active policies do not change: `ACTIVE_BINARY_POLICY` and `ACTIVE_FOUNDER_ATTACH_POLICY` stay `"P0"`. This is not a
legal review, and it claims no legal certainty.

## Founder intent

- **Directive of 2026-10-22, re-issued 2026-10-30:** finish #201's open-source metabolism, repair its defects.
  Section VII lists the expression semantics this record covers.
- **Rules this work keeps:** an unknown license is never cleared automatically. A restrictive term is never hidden
  by an unknown one beside it. AGPL is open source with conditions, not illegal. A founder signature never creates
  rights a license withholds. `packaging.licenses` still validates and canonicalizes every SPDX expression. It
  exposes no expression tree, so evaluating AND/OR stays GREG's residual, as `_evaluate` already was at `a1d2abf`.
  That evaluator is now shared with DEP-5 short names, which `packaging` does not parse. No SPDX list or engine is
  copied.

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
  - a stand-alone License paragraph still applies to nothing;
  - a header License summary that disagrees with the Files stanzas is recorded as uncertainty, and both apply.

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

**Test file:** `tests/unit/test_greg_license_expressions.py`, 1,836 tests. Run against `a1d2abf`'s
`greg/licensing.py`, 1,811 fail and 25 pass (`license-expressions-fail-before.txt`, beside this record). The 25 that
pass are cases with no defect at `a1d2abf`, kept as non-regression pins. Of the 1,811 failures:

- 61 named cases, each listed in that file with its assertion;
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
equivalent new code; 18 entries are new.

- **First run:** every `greg/licensing.py` mutant in the group (42) was run with the gate's own `_run_one` against
  the group's tests. 40 were caught; 2 survived:
  - "restrictive license families are unclassified at other versions": the family table was redundant with the
    rider patterns already applied to unlisted names. The table was removed, and the mutant now removes the
    patterns from the name lookup.
  - "a second License line in one DEP-5 paragraph overwrites the first": the test put the restrictive line last,
    where an overwrite keeps it. The test now puts it first and checks both terms.
- **Rerun:** both caught. All 42 were rerun on commit `4f995317`: 42 caught, 0 survived, 0 stale.
- **Added afterwards:** the 43rd mutant, for the DEP-5 header disagreement, is caught too. Every line of output is in
  `license-mutants-2026-10-30.txt`.

## Limits

- Only what a package declares about itself is read. A false declaration, or a rider inside a full license
  text, is not detected.
- DEP-5 assumes every Files stanza reaches the binary. GREG cannot tell which source files a binary was built
  from, so this side is conservative.
- An exception name containing the word `and` or `or` splits into two names. That is conservative: the extra name
  is unknown.
- Source-available and restricted-use terms stay `incompatible` in the use verdict, and a D-LIC-1 clearance needs
  permission evidence for both. The category changes only the reason: for a source-available term, that evidence
  may be the license's own grant (internal, non-production or non-service use) read against GREG's use.
- Under P4c (a draft, not active), a card qualified before these trees existed is requalified once: its terms now
  carry trees, so the assessment digest differs.

## Independent verification of `083c91ea`, and the fixes

A separate verification lane, with its own extracts of `a1d2abfb` and `083c91ea`, reproduced every claimed fix.
It also found ten defects (`verification-083c91ea.json`, beside this record). It ran a 20,000-case differential
fuzz, a 605-file DEP-5 corpus diff and its own reproductions. Two of the defects are regressions against
`a1d2abfb`, both in the direction of clearing what was held. All ten are fixed here. Each has a test that fails on
the committed head (`verifier-findings-fail-before.txt`: 26 failed) and passes after.

| # | Finding | Fix |
| --- | --- | --- |
| V1 · regression | The inclusive mask cleared "Commercial and non-commercial use require a separate license" | The mask applies only to a sentence that grants; a sentence with restricting words (require, prohibit, separate license, without permission, fee) keeps its phrase |
| V2 · regression | A License line before its Files line was cut off, and P0 attached an AGPL binary | Field order inside a paragraph is not significant (deb822). Only a second Files line, or one in the header paragraph, starts a stanza |
| V3 | An unparseable field lost multi-word restrictive names ("Server Side Public License (MongoDB)") | The fallback also applies the riders to the whole text |
| V4 | `Elastic-2.0` in free text, `SSPLv1` and `BUSLv1.1` cleared beside a classifier | Version-tolerant SSPL and BUSL riders; the `Elastic-2.0` id is matched in free text |
| V5 | An unparseable License-Expression returned before the classifiers and the License field were read | It is unknown, its riders count, and the declarations beside it are read as for a valid one |
| V6 | Unlisted restrictive classifiers beside an expression cleared silently; a non-commercial classifier was absorbed by a BUSL alternative | Shareware, Free To Use But Restricted and AFPL are listed as not open. A non-OSI classifier GREG does not list counts as unknown, and an unlisted OSI one is recorded. A restrictive non-OSI classifier never "agrees" with an alternative |
| V7 | A name only like a known family ("AGPL-3+-with-customer-terms") was read as that family, so the P4c draft found it compatible; an unknown addition to AGPL was dropped | Such a term is marked `unlisted`. It keeps its class, so P0 still holds it, but its use verdict is uncertain and the uncertainty names it |
| V8 | OR: the P0 hold was not monotone; the use election depended on operand order and ignored class | With no cleared alternative, a known restriction in any alternative holds. This reverses the earlier "avoidable restriction" choice: an unknown alternative is not evidence the restriction can be avoided. The use election breaks ties by class, then held terms, then the terms themselves |
| V9 | About 200 nested parentheses raised RecursionError | Nesting past 32 levels is unparseable and fails closed |
| V10 | Two inaccuracies in this record | Corrected below |

**Measured on this host after the fixes:** 0 verdict or class changes across 65 test-venv and 87 system-Python
distributions, 605 DEP-5 files and 1,159 binaries in `/usr/bin`, comparing the committed head with the fixed tree.
The fixes close defect classes that real metadata here does not trigger, as the original fixes did.

**Errata (V10).** The original wording is kept above. The corrections:

- "834 DEP-5 copyright files in `/usr/share/doc`": there are 834 copyright files. 606 carry a Format header, and 605
  parse as DEP-5.
- SPDX-1 and SPDX-2 each say "plus the P0 attach test" fails at `a1d2abf`. Those two tests fail there only with
  `AttributeError`, because `binary_assessment` does not exist at `a1d2abf`. The behavioural fail-before for SPDX-1
  and SPDX-2 rests on the parametrized `deb()` cases and on the review's `system_binary` reproduction.

## The metabolism gate on the fixes (`01f7f7e9`)

The metabolism group ran 98 mutants on `01f7f7e9`. It caught 96; two survived, both in `greg/licensing.py`:

- **"An unparseable expression hides its restrictive names" exposed a real defect.** A Python package's
  `License-Expression` or one-line `License` field that packaging rejects ("EUPL-1.2 AND (MIT") was read only for
  restrictive wording. EUPL, OSL and JSON are restrictive only by GREG's table, so beside an MIT classifier the
  package was CLEARED. DEP-5 already read such a field word by word through `_tree`'s fallback, but no test named a
  license that wording does not also catch.
- **"The use election depends on operand order" was a test gap.** No test had OR alternatives tied on verdict, class
  and held terms, so the final tie-break by name went unheld.

**Fix (`059c734c`).** `_named_restrictions` reads the licenses an unparseable Python declaration names, word by word
from GREG's table. Exact names only: a word is never read as restrictive wording, so "MIT. Free for commercial and
non-commercial use." stays cleared. Each part has a test:

- `test_v11_an_unparseable_expression_keeps_restrictive_names_no_rider_reads`: EUPL-1.2, OSL-3.0 and JSON in a DEP-5
  field, a `License` field and a `License-Expression`; 3 failed on `01f7f7e9`.
- `test_v8_...`: now also has a whole tie in both operand orders.

Three mutants guard the change. The two survivors and the three new mutants were run through the gate's own harness:
all 5 caught. The group now holds 101 mutants, every anchor applying once.

**Measured on this host against `01f7f7e9`:** 0 verdict or class changes across 65 test-venv and 87 system-Python
distributions, 605 DEP-5 files and 1,159 binaries (`named-restrictions-real-diff-venv.json`,
`named-restrictions-real-diff-system.json`).
