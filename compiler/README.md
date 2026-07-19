# compiler

Layer 1 — Executable Constitution. The narrow UCL compiler: constitutional
doctrine in, deterministic policy requests out. Not a general programming
language.

UCL authorizes. Application code executes. Nothing here makes an effect real.

## Interface

- `ucl_parser.parse(text) -> list[Block]` — pure tokenizer + recursive-descent
  parser for HCL-compatible UCL. Malformed input raises `UCLSyntaxError`
  (fails closed, never repairs).
- `ucl_compiler.compile_constitution(root) -> CompiledConstitution` — compiles
  `/constitution/*.ucl` + `/authority/*.yaml` into the deterministic artifact.
  Contradictions between doctrine files raise `CompilationError`.
- `ucl_compiler.compile_to_file(root, out_path) -> constitution_hash`

## Compilation targets (docs/UCL.md)

1. Policy decisions (`rules`, OPA-style, deny by default)
2. Relationship tuples (`relationship_tuples`, OpenFGA-style)
3. Workflow constraints (via policy engine states)
4. Model-checkable invariants (`invariants`)
5. Runtime grant contract (`grant_contract`)
6. Audit schema references (`audit_schemas` → `/contracts`)

Compiled around the ten dimensions: principal, action, resource, context,
legal principal, evidence, budget, consequence class, capability, expiration.

## Buildability standard (14 conditions)

- **Existing mechanism**: recursive-descent parsing + deterministic emission; no novel science.
- **Defined interface**: inputs = doctrine files; outputs = `CompiledConstitution` (typed dataclass, JSON-serializable).
- **Bounded authority**: compiles law; holds no authority itself; cannot execute anything.
- **Available dependencies**: Python 3 stdlib + PyYAML only.
- **Security model**: pure functions, no I/O beyond reading doctrine; malformed input fails closed; determinism makes tampering visible as hash changes.
- **Failure modes**: `UCLSyntaxError` (malformed UCL), `CompilationError` (doctrine contradiction); both terminal, never warnings.
- **Acceptance tests**: `tests/unit/test_ucl_compiler.py` (determinism, ranks, prohibitions, tuples, contradiction refusal).
- **Recovery path**: recompile from doctrine at any time; artifact is derivable, never primary state.
- **Resource ceiling**: compiles the full constitution in milliseconds; memory bounded by doctrine size.
- **Operating cost**: zero per-call cost; measurable via wall time in tests.
- **Legal operator**: Alfonso Lopez (doctrine is his law; the compiler only renders it).
- **Handoff state**: artifact is content-addressed JSON; any engineer can recompile and diff.
- **Replaceable**: swap the parser/compiler without changing policy semantics; the constitution hash pins equivalence.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `compiler` (technical,
authority, evidence, economic, regenerative) and `verifier/v2/verify.py`.
