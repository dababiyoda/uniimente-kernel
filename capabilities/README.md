# capabilities

Layer 5 — Portable Capability Organelles, fully described by genomes.

## Organs

- `genome.py` — `CapabilityGenome`: name, version, interface
  (inputs/outputs), contracts consumed (from `/contracts`), authority
  envelope (max consequence class, budget ceiling, human requirement),
  acceptance tests, failure modes, recovery path. A capability with an
  incomplete genome does not instantiate anywhere; financial/irreversible
  envelopes must require a human; UNIIMENTE is never the operator.
- `genome.py` — `GenomeRegistry`: the kernel's genome library.
  `may_instantiate()` is a bounded-authority check: the request must fit
  INSIDE the registered envelope (class and budget), else refused.

## Recorded proof

`tests/unit/test_capabilities.py` (8 tests): complete genome registers;
incomplete genomes refused (missing tests, broken interface, unknown
contracts); unbounded authority refused; UNIIMENTE operator refused;
class/budget above envelope refused; unregistered capabilities never
instantiate.

## Buildability standard (14 conditions)

- **Existing mechanism**: capability descriptors / plugin manifests — standard, no novel science.
- **Defined interface**: `GenomeRegistry.register/get/may_instantiate`; genomes are pure data.
- **Bounded authority**: envelopes declare maximum class + budget + human requirement; instantiation checks are advisory-bounded, gate-enforced downstream.
- **Available dependencies**: Python 3 stdlib.
- **Security model**: registration refuses incomplete genomes; instantiation refuses anything outside the envelope.
- **Failure modes**: `GenomeError` on invalid genome; `(False, reason)` on out-of-envelope requests.
- **Acceptance tests**: `tests/unit/test_capabilities.py` (8 tests).
- **Recovery path**: genomes are data — a bad registration is refused, never patched; version bumps are new registrations.
- **Resource ceiling**: one ledger append per registration; lookups O(1).
- **Operating cost**: constant.
- **Legal operator**: Alfonso (named on every genome).
- **Handoff state**: the genome itself + ledgered registration records.
- **Replaceable**: envelope values and contract lists are data; registry survives any genome swap.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `capabilities`.
