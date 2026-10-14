# External Wedge Options (evidence-backed, not selected)

Status: **proposal**. Nothing here is achieved, mandated or accepted by any external actor.
This document exists so independent software work does not wait on venture selection, and
so the lawful market ambition stays explicit and separate from current achievement.

Governing frame (spider-web): *Actor A must obtain Outcome B, but completion is unreliable
because governing state C is broken.* Each option names the transaction, the artifact, the
consequence, what exists in the repositories today, what is missing, the cheapest 90-day
falsification test, and the checksum items that are unresolved. Evidence labels follow the
skill: verified fact (primary source), external context (secondary source, verify before
reliance), implementation (code in a UNIIMENTE repository), working assumption.

## W1. Proof-bound model/part promotion for small teams running local open models

- **Transaction.** A small team operating an AI agent must replace or upgrade a model or
  prompt component in a running system without silent behavior change; completion is
  unreliable because fitness proof, identity of the executable artifact, and rollback are
  not bound to the promotion decision.
- **Artifact.** A content-addressed dossier (deficit, diagnosis, search record, shadow
  evidence with typed failures, verifier tier) plus a ratified binding receipt bound to the
  artifact digest. **Implementation:** this is `egregore/genesis.py` + `egregore/parts.py`
  (sandbox tier, PR #129).
- **Consequence.** The promotion decision itself; and, for teams integrating general-purpose
  models in the EU, the technical-documentation duties downstream of Article 53. **External
  context (verify against the Official Journal):** Article 53 obligations apply to new models
  from 2 August 2025 with Commission enforcement powers and fines from 2 August 2026
  ([Arnold & Porter](https://www.arnoldporter.com/en/perspectives/advisories/2025/08/does-your-company-have-eu-ai-act-compliance-obligations),
  [WilmerHale](https://www.wilmerhale.com/en/insights/blogs/wilmerhale-privacy-and-cybersecurity-law/20250724-european-commission-issues-guidelines-for-providers-of-general-purpose-ai-models),
  [AI Act Service Desk FAQ](https://ai-act-service-desk.ec.europa.eu/en/faq)). Open-source
  models get partial documentation relief absent systemic risk, so the pull is strongest for
  teams composing hosted or fine-tuned models.
- **Nearest precedent / counter-position.** Model registries with stage or alias transitions
  and approval requests (MLflow legacy stages; Unity Catalog champion/challenger aliases)
  ([MLflow registry docs](https://mlflow.org/docs/1.3.0/registry.html),
  [Databricks workspace registry](https://learn.microsoft.com/en-us/azure/databricks/machine-learning/manage-model-lifecycle/workspace-model-registry)).
  They track versions and approvals; located descriptions do not bind admissibility to a
  recorded search ladder, bind decisions to a reviewed content hash, or type failures at the
  raising site. A registry vendor copying this would have to make promotion refusable by
  evidence their customers currently skip; that is the self-harm constraint to test, not
  assume.
- **Missing.** A buyer and a mandate-capable actor; any external acceptance of the dossier;
  measured time/cost of a live case.
- **90-day falsification test.** Three teams run one real model swap each through the loop
  (shadow ≥ 3 distinct successes, dossier read, ratified). Number to change: share of swaps
  with a reviewed dossier before promotion (0 → 100 % inside the pilot) and rollback time.
  Terminate if no team completes a swap or none would pay for the receipt.
- **Checksum.** 1, 3, 4, 5, 6, 7, 12, 13 resolvable now; 2, 8, 9, 10, 14, 15, 17 unresolved.
  Form: Tool. **Decision: Validate.**

## W2. Evidence-governed publishing receipts (DALEOBANKS)

- **Transaction.** An organization must publish a claim-bearing update whose provenance and
  AI involvement are accepted by platforms and newsrooms; completion is unreliable because
  provenance is stripped or unverifiable and disclosure duties are growing.
- **Artifact.** A Gate receipt (DALEOBANKS already publishes only through the Gate with a
  judge pipeline and correction duties; **implementation**) plus a signed content credential.
  **External context:** the C2PA Conformance Program launched publicly in October 2025 and
  major news organizations sign content, while platform display and metadata preservation
  remain inconsistent
  ([Content Authenticity Initiative](https://contentauthenticity.org/blog/the-state-of-content-authenticity-in-2026),
  [adoption tracker, secondary](https://editorsweblog.org/2026/04/12/c2pa-adoption-tracker-platforms-content-credentials-2026)).
  A reported October 2026 signature-preservation vulnerability must be checked against the
  specification before relying on credentials for consequence
  ([Wikipedia summary, unverified](https://en.wikipedia.org/wiki/Content_Credentials)).
- **Consequence.** Platform labeling, newsroom acceptance, and disclosure compliance.
- **Missing.** A C2PA signing adapter in DALEOBANKS; a buyer; evidence that any platform or
  newsroom changes a decision because of the receipt; the counter-position against platforms
  bundling their own labels (value must rest on independent verification and correction
  duties they will not own).
- **90-day falsification test.** Sign N posts with credentials and Gate receipts; measure the
  share whose credentials survive upload on two platforms and whether one newsroom or buyer
  accepts the receipt for a decision. Terminate if credentials are stripped everywhere tested
  and no acceptance appears.
- **Checksum.** 1, 5, 7, 12 resolvable now; 2, 3, 4, 6, 8, 9, 10, 15 unresolved. Form:
  Vertical Workflow candidate. **Decision: Validate after the adapter exists.**

## W3. Adversarially underwritten venture assessments (WealthMachineIntelligence)

- **Transaction.** A micro-investor, accelerator or founder must decide whether to fund or
  pursue a small venture; completion is unreliable because claims are unverifiable.
- **Artifact.** A `VentureAssessment` with eleven preserved routes and an eight-sided tribunal
  report (**implementation:** WMI assessment path and kernel `foundry/`).
- **Missing.** Buyer, acceptance, any external anchor (no market research was run for this
  option in this session). **Working assumption** only.
- **Checksum.** 1, 3 resolvable; most others unresolved. **Decision: Park** pending a named
  buyer conversation.

## Not candidates under the safety and legality maximand

- **PumpStation** (memecoin coordination): securities and market-abuse exposure conflicts with
  the lawful-option constraint; parked, not pursued.
- **RailScout**: README states only "Egregore organ"; no transaction identified.
- **RESEARCH-IN**: a research platform without a governing transaction; no wedge identified.

## Decision for the Egregore

**Stage-gate.** Internal control of capability formation is complete at sandbox tier (PR #129).
The external wedge requires a founder decision among W1–W3 (or another transaction). W1 is
the only option whose software already exists; its 90-day test needs three teams and no new
infrastructure. Nothing above establishes market advantage; only external acceptance does.
