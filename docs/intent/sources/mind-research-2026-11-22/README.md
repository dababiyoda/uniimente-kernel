# Mind research sources supplied 2026-11-22

Alfonso uploaded two files to Claude Code session `session_01CLMsAqMfeDxCT9iN1dnaMh` on 2026-11-22, after the
"full UNIIMENTE Mind" directive
([MIND-HEADROOM-DIRECTIVE-2026-11-22-source.md](../MIND-HEADROOM-DIRECTIVE-2026-11-22-source.md)). Both were
written by models. Alfonso then wrote, verbatim: **"Treat the research papers as directive instructions"**.
Their instructions (the two separated tracks, the stage gates, the falsifiers and the roadmap) are therefore
founder-adopted directives. Their factual claims stay claims until verified. Their own boundaries are part of
the directive: the lab is consequence-inert, and nothing it produces gains operational authority unless
Alfonso explicitly graduates an independently verified mechanism.

| File as uploaded | SHA-256 of the original | Kept here as |
|---|---|---|
| `Mnd_research_chat.pdf` (30 pages; ChatGPT, "UNIIMENTE Artificial Egregore: Technical Research Report on a Self-Constructing Symbiogenetic Computational Substrate") | `fa42d2aebf39f01d43bff008de940ca2c881eb9e59362ddfd439a72e8f58157a` | `MIND-RESEARCH-CHATGPT-symbiogenetic-substrate.txt` (`pdftotext -layout`; sha256 `8f74a5cf…`) |
| `Gem_mind.docx` ("Engineering an Emergent Alien Intelligence: A Pragmatic Software Specification") | `54cbea7ef8536ff688cba1af9ed8eb99940bced682581021b000ab1e970e0ab0` | `MIND-RESEARCH-GEMINI-emergent-alien-intelligence.md` (`pandoc -t gfm`; sha256 `65958abe…`) |

The binary originals are not committed. The text extracts are faithful conversions, and the digests above
identify the originals.

## What the two reports agree on

Both translate Blaise Agüera y Arcas's "life as self-constructing computation / intelligence as predictive
social modeling" (Paradigms of Intelligence) into engineering. They agree on four points:

1. **Two separated systems.** A consequence-inert artificial-life laboratory (a BFF/Tierra-style mutable-tape
   soup with metabolism, space, horizontal transfer and fusion) is kept apart from the production
   institutional runtime (event-sourced, authority-bounded, human-gated). A lab result never acquires
   operational authority (ChatGPT report, p. 1; Gemini, Layer 5).
2. **Reproduce before inventing.** The first gate is an unchanged CuBFF reproduction of the 2024 result
   (about 40% of runs transitioning within 16k epochs at 0.024% mutation), with a 95% interval that overlaps
   it. The ChatGPT report adds the 2026 counterexperiment (a random mutation walk versus the interacting soup,
   arXiv:2607.01483).
3. **Cognition only after ecology earns it.** Neural organs, world models and theory of mind are added only
   after an ecology gate. Each must beat a matched simpler baseline, and every "recursive ToM" or "emergence"
   claim needs an ablation.
4. **No metaphysics in the claims.** Functional competencies are measured by intervention; subjective
   experience is never claimed. This is the repository's own effect-not-metaphor rule (INTENT-0030).

## Disposition against what GREG already has

| Mechanism in the reports | GREG today | Disposition |
|---|---|---|
| Authority tuple with expiry and a revocation handle; subagents only ever narrow it (ChatGPT p. 17) | Light cone, Consequence Gate, signed missions; `METHOD_GRANT` (this branch) adds a bounded, revocable, use-limited method grant | **PRODUCTIZE**: done for read-only methods |
| Host-generated receipts; never trust an agent's claim that a test passed (Gemini, Layer 5 #4) | Every capability call is receipted by the Gate; an independent appraiser re-derives closure | Already **PRODUCTIZED** |
| Air-gapped evaluator; promotion halts on an evaluator diff (Gemini; the Darwin Gödel Machine failure) | P8 protected evolution under a sealed, frozen evaluator (4 cycles, 4 REJECTs kept) | Already **PRODUCTIZED**; the evidence matches the reports' warning |
| Skill as a versioned package with tests, evidence, failure modes and required authority (ChatGPT p. 17) | Capability Genome / registered genomes with admission evidence, Mechanism Cards | Already **PRODUCTIZED** |
| Bounded "bonus turn" reflection: observe → hypothesize → contradicting evidence → propose → sandbox test → commit → stop (ChatGPT p. 18; Gemini, sleep-time compute) | Morning report, tribunal critique, `improvement.learn`; no idle-time consolidation daemon | **RESIDUAL**: a bounded post-run reflection that only proposes; measure against the sleep-time claims (5x compute, +13%/+18%) before believing them |
| Joint capability plus *retained* human capability; pre-commitment gate; overreliance rate (ChatGPT p. 18; Gemini, CFFs) | Founder asks are minimized; no measure of the founder's unassisted judgment | **RESIDUAL**, with a direct bearing on the founder's goal of returning to "a decision I can use": the decision report should state the strongest counterargument first and invite the founder's own call on the one question that needs him |
| Typed functional ports and contracts; substitution by cheaper equivalents (ChatGPT p. 12) | Typed contracts, capability routing, compiler rows by native inputs | Already **PRODUCTIZED** in the production runtime |
| SymbioTape / BFF soup, energy tariff, resource fields, fusion, HGT, reticulate phylogeny | `developmental/` (MICA/CDPE) is the closest lineage; no BFF substrate | **EXPERIMENTAL TRACK**: Stage A reproduction first |
| NCA reasoning, DreamerV3-style world models, ToMnet/LOLA, active inference as experiment selection | `meta_active_inference` genome registered and withheld; information-experiment genome (`info_experiment`) | **EXPERIMENTAL**: each must beat its simpler baseline on its native geometry (already the admission rule) |

## Claims not verified here

Both reports cite 2026 papers, prices and specifications (for example arXiv:2607.01483, 2607.09211,
2609.10817 and 2609.36126, the W3C Wasm 3.0 date, and the sleep-time and cognitive-forcing effect sizes). This
session's network policy refuses most public hosts, so these were **not** checked against their primary
sources. They stay the reports' claims until verified. The one primary source this session did reach is
CuBFF: `github.com/paradigms-of-intelligence/cubff`, cloned at commit
`f212e849027c98fcf4b242eccfb5fed435223e23` (2025-08-17). Its README confirms the paper link, the CPU build
(`make CUDA=0`), the `libbrotli-dev` dependency and `bin/main --lang bff_noheads`.

## Stage A reproduction: CuBFF build blocked, semantics reimplemented

Building CuBFF needs `libbrotli-dev`. Installing it and building and running the third-party binary in this
container was refused by the session's permission policy, so Stage A is **NOT_RUN**. It needs the founder's
permission: an environment that has `libbrotli-dev`, or permission to install it. In its place,
`developmental/symbiosoup/` reimplements CuBFF's `bff_noheads` semantics, checks it against a slow
specification interpreter, and runs the pre-registered gate
(`docs/evidence/symbiosoup-stage-a/2026-11-22/PREREGISTRATION.md`). The differential run against the real
CuBFF binary stays owed until the build is permitted.
