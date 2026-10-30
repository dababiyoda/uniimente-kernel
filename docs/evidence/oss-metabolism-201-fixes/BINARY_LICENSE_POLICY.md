# Binary license policy: four options measured for founder decision D-LIC-2

Status: comparison and recommendation only. `greg.licensing.ACTIVE_BINARY_POLICY` stays `"P0"` and
`ACTIVE_FOUNDER_ATTACH_POLICY` stays `"P0"`; nothing here changes which policy is active. This is not a legal
opinion. It extends `docs/open-source/BINARY-LICENSE-POLICY-2026-10-22.md` and corrects one of its successors'
measurements (below).

## The question

Genesis acquires installed operating-system binaries. Their licenses are read from the Debian DEP-5 copyright file
of the package that owns them, and often GREG cannot classify them; on a body without dpkg (macOS) nothing is
readable. May such a binary attach under a founder-signed read-only mission scope without the founder's own
`CAPABILITY_ATTACH`?

Founder rules that bound every answer:

- building is not installation, installation is not activation, and activation is not consequence authority;
- an unknown license is never cleared automatically;
- a restrictive term is never hidden by an unknown one beside it;
- AGPL is open source with conditions;
- a signature never creates rights a license withholds.

Under P0 today, an unclassified binary attaches "as before licenses were read". That is the exception this
decision is about.

## What GREG actually acquires (measured)

- **Catalog** (`greg/genesis.py`, `CATALOG`): three functions, five binaries and one companion.
  - `hash.sha256`: `sha256sum` (coreutils), then `shasum` (perl), then `openssl`, tried in that order.
  - `text.wordcount`: `wc` (coreutils).
  - `document.text`: `pdftotext`, with `pdfimages` as its companion (both poppler-utils).
- **Tests.** The 80 test files that mention Genesis, acquisition or auto-attach were run once with every DEP-5 read,
  binary lookup and attach check logged (1,606 tests ran; the errors in that run come from the logging plugin and
  from running outside a git checkout, not from licensing).
  - Real binaries whose license was read: `pdftotext` and `pdfimages` (poppler-utils, 25 reads), `sha256sum` (8)
    and `wc` (2) from coreutils, and `shasum` (perl, 1).
  - `shasum` is reached only by `test_detached_tool_is_replaced_by_independently_verified_alternative`. That is the
    self-repair route: after the founder detaches `sha256sum`, Genesis forms `hash.sha256` again from the next
    candidate.
  - `openssl` was never reached. Two fake `sha256sum` scripts in temporary directories (the lying-tool tests) had
    no dpkg owner.
- **Chromebook path.** `greg/chromebook/install.sh` installs Python dependencies and no binary.
  - Crostini's Debian container ships coreutils.
  - `pdftotext` needs the founder's own `sudo apt install poppler-utils` (`DOCUMENT-TEXT-2026-10-22.md`).
  - Whether the founder's container has perl's `shasum` and `openssl` was not observed: the Chromebook was not
    available to this session.
- **Other system tools.** GREG runs `git`, `node`, `bwrap`, `systemctl`, `security`, `ollama` and `claude`
  directly. These are not acquired through Genesis, and no binary-license policy applies to them today.

## The four options

- **O1, fail closed.** A newly acquired binary attaches by itself only when its verdict is CLEARED or
  CLEARED_WITH_OBLIGATIONS. Unclassified, undeterminable and held binaries wait for the founder.
- **O2, reviewed allowlist.** O1, except for (package, binary) pairs a person has reviewed for GREG's use. The
  measured list is the catalog's five pairs that are indispensable today: coreutils `sha256sum` and `wc`, `openssl`,
  and poppler-utils `pdftotext` and `pdfimages`.
- **O3, use context plus authenticated approval.** The existing drafts. P4c attaches automatically only when every
  term of the binary and its companions is compatible with GREG's actual use. D-LIC-1 lifts a hold only with a
  founder-signed `license_clearance` bound to the assessment digest, the use, a basis and every obligation, plus
  permission evidence for a not-open term.
- **O4, distributor-reviewed component (the strongest simple alternative found).** It has three parts:
  - a known network-copyleft or not-open term holds, exactly as in P0;
  - an unclassified binary attaches only when apt says the installed package version is served by a distributor
    archive whose policy admits only free software: Debian `main`, Ubuntu `main` or `universe`. That is the
    Release file's `Origin` and `Component`, which apt verified against the source's key;
  - GREG's use must be the present one: unmodified, a separate process, no network, not redistributed, read-only.

  Everything else waits for the founder: non-free, contrib, restricted, multiverse, a third-party archive, a
  locally installed `.deb`, or a body without a package manager.

## Measurements

Body: this cloud container, Ubuntu 24.04 with dpkg, 2026-10-30. Reproduce with
`PYTHONPATH=. python docs/evidence/oss-metabolism-201-fixes/measure_binary_policy_options.py`; the output is
`binary-policy-measurement.json` beside this file.

**Sample.** 708 executables in `/usr/bin`. Their packages come from:

| Origin of the package | Binaries |
| --- | ---: |
| `Ubuntu/main` | 641 |
| `Ubuntu/universe` | 48 |
| `Docker/stable` (a third-party archive) | 7 |
| local: no configured archive carries the installed version | 9 |
| no dpkg owner | 3 |

| | P0 (active) | O1 | O2 | O3 (P4c + D-LIC-1) | O4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `/usr/bin` binaries held (of 708) | 0 | 443 | 443 | 443 | 15 |
| Catalog binaries held (of 6) | 0 | 1 (`shasum`) | 1, or 0 once `shasum` is reviewed in | 1 (`shasum`) | 0 |
| Self-repair after detaching `sha256sum` | repaired with `shasum` | waits for the founder; `openssl` never tried | as O1 unless `shasum` is listed | waits; clearance route exists; `openssl` never tried | repaired with `shasum` |
| Body without dpkg (macOS) | all attach, nothing read | all held | allowlist by name unusable; by digest it breaks on every upgrade | all held | all held |

O4's 15 holds:

- 3 binaries from the third-party Docker archive (`docker`, `dockerd`, `docker-proxy`);
- 9 from Python 3.11 and 3.13 packages whose installed version no configured archive serves (`python3.11`,
  `pydoc3.13`, and others);
- 3 with no dpkg owner (`man`, `nc.openbsd`, `pg_config`).

None is a catalog binary.

O2 holds as many binaries as O1 here because every allowlisted pair is already cleared. Its only effect on today's
catalog is `shasum`, if a person reviews perl's 11 unclassified license names and adds it.

**Suites under each policy.** The body's acquisition suites were run under each option through a test-only plugin:
`test_greg_document_text`, `test_greg_missions`, `test_greg_genesis_negative_control`, `test_greg_verify_download`,
`test_greg_founder_and_scope`, and the P0 self-repair pin from `test_greg_binary_policy_options`.

| Policy | Result (of 79) | Self-repair (functional regression) | Tests that state P0 itself | Containment tests using a hand-made binary |
| --- | --- | --- | --- | --- |
| P0 | 79 pass | none | pass | pass |
| O1 | 75 pass, 4 fail | 2 fail: the founder-detach repair waits | 2 fail: they state P0's rule, or the hold reason's wording | pass |
| O3 (P4c) | 71 pass, 8 fail | 2 fail: the same | 2 fail | 4 fail: no package owns the binary, so no use qualification is recorded and requalification refuses the run |
| O4 | 78 pass, 1 fail | none | 1 fails (`test_a_binary_is_held_only_on_a_known_uncleared_license`: a card with no binary path has no package, so O4 holds it) | pass |

O2 was not run separately: for these suites it equals O1 unless `perl`/`shasum` is reviewed onto the list, and
then it equals P0.

**Cost.**

- O1 and O2 add nothing at attach time.
- O3 adds about 38 ms per binary per run: one `dpkg-query` and one DEP-5 read, measured 2026-10-23.
- O4 adds one `apt-cache policy` per package at qualification, about 1.5 s here, plus about 1.5 s once to map apt's
  sources. Both were measured under a load average near 7 on 4 cores. Cached by package version, O4 costs nothing
  per run.

## A measured defect behind the fail-closed options

Under P4c, and equally under O1, a license hold on one candidate ends the repair. With `sha256sum` detached and
`shasum` held, Genesis records "its license needs your decision" and stops. It never tries `openssl`, which is
Apache-2.0 and cleared, so the mission waits for the founder although a cleared tool is installed.

`test_under_p4c_a_license_hold_on_one_candidate_does_not_end_self_repair` records this as a strict `xfail`. It
starts to pass, and must be unmarked, once Genesis tries the next candidate.

This corrects `use-context-measurement-2026-10-23.json`, which records `functions_lost_under_p4c: 0`. That counted
which binaries are installed, not the repair route that reaches them.

The fix belongs in the candidate loop around `Genesis._attach` (`greg/genesis.py`), which other #201 lanes and the
integrator own; it is not made here. A license hold should be recorded and the search should continue, escalating
only when no candidate attaches. Every fail-closed option (O1, O2, O3) needs this fix before activation.

## Comparison

| Option | Legal-supply-chain risk | Regression risk to the founder's body | Ongoing work |
| --- | --- | --- | --- |
| P0 (active) | Highest. An unread AGPL or proprietary binary, a third-party archive's binary, or a local `.deb` attaches by itself whenever its license names are unclassified. On macOS nothing is read at all | None | None |
| O1 | Lowest for acquired binaries | `shasum` self-repair lost on Debian-family bodies (and, until the defect is fixed, `openssl` is not reached either); every acquired binary held on a body without dpkg; 63% of `/usr/bin` held | A founder decision for each held binary |
| O2 | Low for listed pairs. A listed package's license can change on upgrade unless the entry is bound to version or digest | As O1 for anything unlisted. Every new binary function needs a reviewed allowlist edit | Allowlist review and re-review on upgrades |
| O3 | Low. Each term is judged against the actual use, rechecked before each run; a founder clearance is digest-bound and needs permission evidence for not-open terms | As O1 today (443 held, `shasum` and the repair defect), plus a requalification stop whenever an OS upgrade changes a copyright file | A founder clearance for each held binary; 38 ms per run |
| O4 | Low to moderate. It relies on the distributor's review that every package in the archive is free software, so use for any purpose is granted, but GREG does not read the exact terms. An archive the founder adds could claim the `Origin` "Ubuntu" with its own key; the evidence is as good as the configured sources | None on this body: catalog 0, self-repair intact. All held on a body without dpkg | None routine. One cached apt lookup per package version |

## Recommendation (a proposal; the founder decides)

The smallest defensible policy is **O4 with three conditions**:

1. **Keep P0's hold** on any known network-copyleft or not-open term. With this branch's expression fixes, an
   unknown neighbour can no longer hide such a term.
2. **Accept the distributor's free-archive provenance only for GREG's present use:** local, unmodified, a separate
   process, no network, not redistributed, read-only.
   - The assessment states it plainly: "terms not classified by GREG; the package comes from <origin>/<component>,
     an archive that admits only free software".
   - When the use widens (network access, linking, redistribution, modification), the binary is judged as in O3,
     so an unknown term holds and a D-LIC-1 clearance is the way through.
3. **Fix the fall-through first**, so a hold on one candidate never ends a repair that a cleared candidate could
   complete.

Why this policy:

- **It closes P0's real exposure.** A binary from a third-party archive, a local package or a non-free component no
  longer attaches by itself: 15 binaries on this body.
- **It loses no function the body uses today:** 0 catalog holds, and self-repair is intact.
- **It needs no allowlist and no per-package review.** It replaces the long tail of license names, which
  measurement showed name tables cannot close, with a review the distributor has already done.
- **On a body without dpkg it is O1.** Nothing is readable there, so nothing attaches by itself. No founder-owned
  body of that kind exists today.

What O4 does not do: it does not classify the terms, and it does not make an unknown license known. It treats an
archive's free-software policy as evidence of the license's category for one use, and it says so on the card.

## Founder decisions required

- **D-LIC-2, the binary policy.**
  - Is a distributor archive's free-software policy, read from apt's verified Release data, acceptable evidence for
    an unclassified license in GREG's present local, read-only use (O4)? Or should "never cleared automatically" be
    read strictly (O1 or O3)?
  - If O4: should bodies without a package manager fail closed?
- **D-LIC-1, the founder attach policy.** Recorded separately; unchanged here.
- **The fall-through fix in Genesis.** This is the owner's or the integrator's change, needed before O1, O2 or O3.

Nothing in this record is enforced. The enforced rule is still P0.

## Limits

- One container. Crostini was not observed, and its package origins will read `Debian/main`.
- The `Origin` field is the archive's own claim, verified only against the key configured for that source.
- The P4c, O1 and O4 behaviour in the sweep comes from a test-only plugin. O4 is implemented only in the
  measurement script, not in `greg/licensing.py`.
- The DEP-5 reader still assumes that every Files stanza reaches the binary (`LICENSE_EXPRESSIONS.md`).
