# Novel Authority Architecture Decision

## C. A new architecture superseded Strategy C.

**Proof-Carrying Authorization.** Authority stops being ambient state inside an engine and becomes a portable, signed, independently verifiable artifact. One issuer signs. Everyone verifies. Every organ may refuse.

Candidates and scoring: [`NOVEL_AUTHORITY_CANDIDATES.yaml`](NOVEL_AUTHORITY_CANDIDATES.yaml).
Implementation: [`aperture/`](../../aperture/). Evidence: [`verification/canonical_authority_rc1/`](../../verification/canonical_authority_rc1/).

```
ACTIVE_CANONICAL_AUTHORITY_PROTOCOLS = 1     Gate A CLOSED
UNEXPLAINED_TEST_COLLECTION_DELTA    = 0     Gate B CLOSED
Gate C: four sandbox proofs pass             Gate C CLOSED
555 tests pass, clean environment, declared dependencies only
```

---

## The decisive evidence

Strategy C was not wrong about *mechanisms*. It was wrong about **geometry**.

Every one of its residual weaknesses traces to a single choice: the gate both decides and executes, in one process, holding authority as in-memory state. That is why the availability objection survived the last adversarial pass, why a remote effector cannot participate, and why composing two engines does not merge their trust roots.

Change that one thing and the objections dissolve together:

| | Strategy C | Proof-Carrying Authorization |
|---|---|---|
| Effector partitioned from Kernel | cannot act, or bypasses | verifies locally with a public key, or refuses |
| On-chain effector | impossible | an Ed25519 signature is verifiable in a contract |
| External auditor | needs system access | needs a public key |
| Bound fields | 3 (main) / 11 (PR21) | **20**, all inside the signature |
| Trust roots | two, unmerged | one, by construction |
| Local veto | organ-side, advisory | independent AND-gate read before execution |

The bouncer-versus-ticket distinction is the whole change. A bouncer must be present and reachable. A signed ticket works when the bouncer is unreachable, names its holder, and can be checked by anyone.

**What made it decisive rather than merely elegant:** it is the only candidate that closes the two attacks that survived the previous pass. Attack 5 (centralizing grant semantics creates an availability hazard) is answered because verification never requires the Kernel. Attack 6 (composing engines does not merge trust roots) is answered because there is exactly one issuing key by construction — a legacy HMAC record cannot produce a certificate, so there is nothing to merge.

## What was promoted, from where

Nothing was discarded for being old, and nothing was kept for having tests.

- **PR #21** — the 11-field fingerprint breadth (widened to 20), fail-closed refusal discipline, typed refusal taxonomy, and the Ed25519 trust root. It earned 24/30 refusals; it deserved to set the standard.
- **main** — constitutional policy evaluation, the identity/passport model, and budget reserve→commit→release with unwinding on every failure path.
- **phase7 SDK** — `named_targets` and `permitted_actions`, the only scope controls in any engine that refused the unknown-target and unknown-capability cases. They became `known_targets` and `declared_capabilities`.
- **DALEOBANKS** — the local fail-closed veto, now a real AND-gate rather than a one-way signal.
- **Nuclear command-and-control doctrine (C9)** — the permissive action link: the *effector* validates the order rather than trusting the courier. Fail toward silence. Positive control stays local.
- **New invention** — the twenty-field Authorization Certificate itself; the signing/verification split as a type-level property; and legacy classification that preserves HMAC history without granting it attribution.

## Superseded thinking, including my own

- **"Compose the three engines" (my own recommendation last pass).** Composition preserved the monolith. The right move was to change what authority *is*, not to merge who holds it.
- **"Line counts show main is behind."** Wrong instrument. main is 355 lines and PR21 is 571, and main expressed 12 fewer hostile cases — but that comparison only became meaningful when both were executed against the same corpus.
- **"The SDK KillSwitch is a working local veto."** False, verified. It was written to and never read. I had assumed otherwise.
- **"Ed25519 is the answer."** Adopted, but not assumed: it is behind a `SigningProvider` interface precisely so the algorithm is replaceable. §14 was right to demand that.

## Adversarial pass — what survives

**SURVIVES — the revocation window.** A certificate valid for 15 minutes is 15 minutes during which revocation depends on an effector reaching the registry it may not be able to reach. Short TTLs mitigate; they do not eliminate. This is the price of partition safety and I have not solved it. Threshold authorization (C7) for the dangerous classes is the mitigation, deferred.

**SURVIVES — the signing key is now the whole institution.** Concentrating authority into one key concentrates catastrophe into one key. `SigningProvider` allows HSM custody and the registry supports rotation, but neither is deployed. Until custody is real, RC1's trust root is an in-process key.

**SURVIVES — no organ has been migrated.** DALEOBANKS, WMI and PumpStation are untouched. The architecture is proven in a sandbox against a fake platform, not against a real organ. Gate C is closed *for the sandbox*, which is exactly what Gate C asks and exactly less than production evidence.

**SURVIVES — main's engine is still importable.** It is retained deliberately as a regression oracle, per the preservation doctrine. Static detection forbids canonical code importing it, but a determined caller inside this repo could still instantiate it. Process isolation is not implemented, so "one authority" is enforced by tests and disposition, not by the operating system.

**FALLS — "the novel architecture has a larger failure surface."** It has a *smaller* one: refusals are local and independent, and no single component can permit. The certificate is inert data.

**FALLS — "it cannot support PumpStation or physical effectors."** The reverse: this is the only candidate that can. A contract verifies a signature; a robot needs a public key and a clock.

**FALLS — "it reduces UNIIMENTE to conventional software."** C10 was the conventional design and it was rejected precisely because a permissions table cannot be verified from outside the institution.

**FALLS — "founder unavailability creates an unsafe permanent stall."** Only REQUIRE_HUMAN classes need the founder; PERMIT classes issue without him. C7 would reintroduce this risk, which is one reason it is deferred.

---

## Founder decisions

### Decision A — admit the RC1 architecture as the canonical authority candidate

```yaml
founder_decision:
  verified_facts:
    - ACTIVE_CANONICAL_AUTHORITY_PROTOCOLS = 1, machine-enforced by 9 tests
    - 51 hostile conformance tests pass; every verified defect has a named regression test
    - 555 tests pass in a clean venv with only declared dependencies
    - four sandbox proofs pass with no credential and no real external effect
  recommendation: >-
    Admit as candidate. Do NOT merge. Migrate one organ (DALEOBANKS publication)
    behind it in shadow mode before anything else moves.
  strongest_objection: >-
    Proven against a fake platform in one repository. No organ uses it. The
    revocation window and key custody are unsolved.
  alternatives: [Strategy C, keep main, containment only - all recorded in the candidates file]
  reversible: true - nothing merged, superseded engines retained and passing
  authority_implications: changes what may authorize an external effect
  affected_repositories: [uniimente-kernel now; DALEOBANKS, WMI, PumpStation later]
  migration: organ by organ, shadow first
  rollback: delete the branch; main is untouched
  smallest_authorized_next_action: review the draft PR
```

### Decision B — legacy HMAC policy

**Recommended default, implemented and tested:** readable, historically preserved, integrity-checked where the secret survives, and **never accepted as new authority**. A passing HMAC check establishes consistency with a historical shared-secret implementation, never signer attribution — everyone able to verify was equally able to produce. See [`TRUST_ROOT_MIGRATION.md`](TRUST_ROOT_MIGRATION.md).

### Decision C — PR #21 disposition

**Recommend: close as superseded, after crediting it.** Its fingerprint discipline and Ed25519 root became the architecture. Its hostile suite is retained as a conformance opponent (`CONFORMANCE_FIXTURE`). Its provenance stays in the disposition registry. It should not merge: merging it would create the second government this pass removed.

### Decision D — phase-train status

**Recommend: classify as historical**, with the SDK's scoping credited as promoted. Gate B established the phase7 merge is purely additive, so nothing is lost by not merging it.

### Decision E — constitutional ratification dependency

**Recommend: RC1 stays a technical candidate until ratification.** It is a stronger implementation of an unratified constitution. That is a real blocker no build session can clear.

---

## What was not done

- `COMMIT_DAG_RECONSTRUCTION.json`, `SDK_MODULE_DISPOSITION.yaml`, `PR21_DISPOSITION.md`, `PHASE_TRAIN_PRESERVATION.yaml`, `PR32_RECOVERY_CLASSIFICATION.yaml`, `FOUNDER_DECISION_RECORD_V2.md` — not written. `aperture/dispositions.py` carries the machine-readable dispositions; Decisions C and D above carry the reasoning.
- `LOCAL_VETO_MODEL.md`, `SDK_BOUNDARY.md`, `MORPHOGENETIC_AUTHORITY_COMPATIBILITY.md`, `RC1_VERIFICATION_REPORT.md` — not written as separate documents. The veto model is in `aperture/effector.py` and Proof C; morphogenetic compatibility is in the candidates file and Proof D.
- **PR #32 was not inspected.**
- **No organ repository was modified.** DALEOBANKS, WMI and PumpStation are untouched.
- **Track B untouched.** No digital cell was granted authority, nothing morphogenetic was moved onto the consequence path, and no production dependency on morphogenesis exists.
