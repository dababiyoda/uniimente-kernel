# DALEOBANKS Shadow Migration

The first real organ behind the Reality Aperture. **Zero real publications.**

Implementation: `DALEOBANKS/governance/aperture_shadow.py` · Tests: `DALEOBANKS/tests/test_aperture_shadow.py` (18) · Evidence: `DALEOBANKS/verification/daleobanks_shadow_results.json`

## Path

```
publication candidate
 -> identity and evidence envelope
 -> policy evaluation              (Kernel)
 -> authorization certificate      (Kernel - the only signer)
 -> certificate verification       (organ, public key only)
 -> revocation validation          (organ, signed snapshot)
 -> ConstitutionGuard              (organ, local)
 -> KillSwitch                     (organ, local, fail-closed)
 -> fake publication adapter       (independent state)
 -> independent readback
 -> receipt -> reconciliation
```

The existing production path in `services/` is **untouched**.

## The organ cannot authorize itself

`Aperture.__init__` takes a `VerificationRegistry` and has **no parameter that accepts a signer** — asserted by test. DALEOBANKS can refuse a publication; it cannot manufacture permission. That is the constitutional relationship expressed as a type signature rather than a rule in a document.

## Independent external state

`FakePlatform` owns its own state. The executor **submits**; the platform decides what it stores; the verifier **reads separately**. The executor has no way to write the value the verifier will read.

Proved: an adapter that claims success and writes nothing produces `reconciliation_mismatch`, not success. A platform that mutates what it stores is caught. Duplicate execution yields one post and a `replay` refusal.

## Results

```
candidates_processed        5      certificates_issued          3
certificates_refused        2      identity_mismatches          1
revocation_refusals         1      legacy_path_agreements       3
legacy_path_disagreements   2      external_publications        0
mean_validation_latency_ms  1.947
```

**`false_refusals` is deliberately unclassified.** Judging whether a refusal was correct requires a human. No automatic classification is made and none is guessed.

**Both divergences from the legacy path are cases where the legacy path would have published and the aperture refused** — one identity mismatch, one revoked certificate. In both the aperture is correct. Preserved as evidence either way, per the rule that a disagreement is not automatically an error.

## Zero real publication, proved

- the adapter registry contains exactly one entry, the fake
- `resolve_adapter` raises `ShadowConfigurationError` on any production adapter
- `assert_no_production_credentials` fails closed on any of the five X credential variables
- no X credential is read, passed, or referenced on this path
- `real_publications()` returns 0

## Packaging gap

The aperture lives in `uniimente-kernel` and is imported from a sibling checkout via `UNIIMENTE_KERNEL_PATH`. That is a development convenience, not a distribution strategy. Until the Kernel publishes an installable client package this module is **not deployable**, and the tests skip rather than pretend.
