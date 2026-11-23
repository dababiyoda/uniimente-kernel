# License qualification bound to use: drafts D-LIC-1 and P4c

Status: **draft, inactive.** `greg.licensing.ACTIVE_BINARY_POLICY` and `ACTIVE_FOUNDER_ATTACH_POLICY` are both
`"P0"`. Activation is a founder-reviewed commit that changes those two constants and the guard test
`test_neither_draft_is_active_until_the_founder_adopts_it`. This record is not that approval, and it is not a
legal opinion.

Founder directive, 2026-10-23: "A bare CAPABILITY_ATTACH must not bypass an unresolved licensing hold." "A
signature does not override third-party rights." "Do not treat absence of network access or redistribution as
proof that all unknown licenses are automatically compatible." "No scanner may declare legal certainty merely
from text classification." "Prepare the implementation and regression tests in a draft. Do not activate the
policy until I explicitly approve it."

## What changed

GREG used to ask whether a license was restrictive. It now asks whether the license allows the use GREG actually
makes of the software, and when that answer has to be asked again.

- **`qualify_use(assessments, use, subject)`.** This judges every declared term against the route's real use. That
  use is `GREG_USE`: an unmodified, separate process, network-isolated, never redistributed, under a read-only
  scope.
  - GPL and LGPL are compatible with that use. AGPL, EUPL and OSL are compatible when the program is run
    unmodified and locally.
  - The same terms become uncertain when the program is redistributed, linked, modified or exposed to a network.
  - Not-open terms are incompatible unless there is permission evidence.
  - An unclassified or unreadable license is always uncertain. The use being local proves nothing about it.
  - The verdict carries `assessment_digest`, which covers the binary hash, its version, the hashes of companion
    binaries and the declared parts, but not prose. It also carries `use_digest`.
- **P4c, the draft binary policy** (`attach_check(manifest, "P4c")`). It allows automatic attach only when every
  term of the binary and of each companion is compatible.
  - `_manifest_for` records `use_qualification` on each Mechanism Card.
  - `catalog_adapter` calls `requalify_binary` before each run. If the license facts or the use differ from the
    qualified ones, the run stops with "requalification required". Under P0 this call returns at once.
- **D-LIC-1, the draft founder-attach policy** (`founder_attach_check`). A capability under a license hold attaches
  on the founder's command only with a `license_clearance` that meets all of these:
  - its assessment digest is exact, so a stale clearance is refused;
  - it names this route's real use;
  - it gives a non-empty basis;
  - it accepts every obligation;
  - for a not-open term, it names `permission` evidence.

  The clearance record goes into the `capability.state` journal entry. A compatible capability needs no clearance.
  AGPL and GPL are never refused merely because they carry obligations.
- **The `body.py` hook** is a single inert call, offered as
  `binary-license-policy-2026-10-22/d-lic-1-body-hook.patch` for the integrator to take in. `greg/body.py` is
  integrator-owned and is not edited by this PR. A test keeps the patch applying cleanly.

## Attach routes covered

| Route | Under the drafts |
| --- | --- |
| `Genesis._attach` (signed read-only auto-attach) | `attach_check` with the active policy |
| `Genesis._attach_dependency` | same |
| `Body` CAPABILITY_ATTACH | `founder_attach_check` through the patch |
| `cognition/benchmark.py`, `cognition/genomes/admission.py` | harness attaches of GREG's own genomes; their provider is not `installed:`, so the policy does not apply |
| Recovery re-admission | the capability returns to VERIFIED and re-attaches through `_attach`, so it is checked again |
| Execution | `requalify_binary` before every run |

## Measurements

Full data: `binary-license-policy-2026-10-22/use-context-measurement-2026-10-23.json`.

- **Holds across all 707 binaries in `/usr/bin`.**
  - P4c holds 442, the same number as fail-closed P1. On whole-machine counts P4c is not cheaper than P1.
  - Its gain is elsewhere: GPL and local AGPL are cleared because of the actual use; the verdict is bound to the
    assessed facts and checked again before each run; and the founder has a lawful clearance route that P1 lacks.
- **GREG's catalog binaries.** P4c holds only `shasum`, whose owning package is `perl`. `hash.sha256` is still
  served by `sha256sum` or `openssl`. Functions lost: 0. Founder decisions with today's catalog: 0.
- **Added latency.** The median is about 38 ms per binary per run under P4c, from one `dpkg-query` call and one
  DEP-5 read, measured under concurrent test load. It is about 0.2 µs under P0.
- **What drives false holds.** The DEP-5 reader does not cover enough license names. The leading unclassified
  terms are ImageMagick, Magick++, "other", "permissive", CC-BY-SA-3.0, bare LGPL and GNU-All-Permissive.
- **Negative result: a bigger name table is not the lever.** Adding 18 version-independent DEP-5 names (bare
  LGPL and Apache, ImageMagick, libpng, Unicode, PHP-3.01 and others) moved P4c from 442 holds to 438. A package
  is held when any one of its terms is unclassified, and the long tail is per-package text ("other", "permissive")
  that only reading the text can classify. The extension was reverted; the measurement is kept here.
- **P3, ScanCode, targeted.**
  - scancode-toolkit-mini 32.5.0 ran in an isolated scratch venv. Nothing was installed on the body's interpreter.
  - The dependency defect reproduces: with pluggy 1.7.0 it fails to start (`did not find any 'pre_scan' hooks`);
    with pluggy 1.4.0 it runs.
  - Cost: a 717 MB venv and a 34 s install. Scanning 4 copyright files took 29.4 s cold, 24.3 s warm, with a
    peak of 1.4 GB of memory.
  - It classifies `perl` as strong copyleft, which would lift the one catalog hold.
  - It disagrees with GREG on `openssl` (weak versus strong copyleft). The disagreement is kept, not resolved.
  - A scan result is text classification, not legal certainty. If adopted, it should be cached by the digest of
    the copyright file and run only on a P4c hold, never on every run.

## Capability dividend, compared with the alternatives

- **Workflow automation (n8n- or Zapier-style).** It can run a license scanner as a step. It does not bind the
  verdict to the binary's hash and the declared use, and it does not stop a later run when either changes.
- **Package managers (dpkg, pip).** They declare licenses. They do not judge a declaration against a use, and
  they do not hold anything.
- **GREG.** It now carries one Mechanism Card per capability that records what the software is allowed to do in
  GREG's use, on what evidence, and when that must be asked again.

No second registry or package manager was added. The record lives on the existing Mechanism Card and in the
Capability Genesis journal.

## Remaining uncertainty

- A false declaration in a DEP-5 file is not detected. The digest only makes a later correction invalidate the
  earlier qualification.
- Whether P4c's 442 machine-wide holds matter depends on which binaries GREG will acquire in the future.
- P4c's latency has been measured only in this container.
- The D-LIC-1 hook has been exercised only as a patch. Its route test runs once the integrator takes it in.

## Kill and rollback

Set either constant back to `"P0"`; the drafts are then inert. Remove `requalify_binary` from `catalog_adapter`
and the `use_qualification` line from `_manifest_for`. The patch is never applied unless the integrator chooses.
Kill condition: if P4c holds a binary GREG needs, with no compatible substitute, more than once per month of real
missions, without a matching true finding.
