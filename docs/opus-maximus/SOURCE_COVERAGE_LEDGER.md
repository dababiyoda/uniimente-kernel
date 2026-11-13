# Source Coverage Ledger — OPUS MAXIMUS one-GREG trunk

Deliverable A. Built 2026-10-15 on branch `claude/opus-maximus-one-greg-20261014`.
Machine-readable companion: [`SOURCE_COVERAGE_LEDGER.json`](SOURCE_COVERAGE_LEDGER.json), one record per source with hash,
read status, document kind, speaker, date evidence, summary, exact founder quotes with line numbers, intent candidates,
contradictions, evidence tier and gaps.

## What was read, and how

| Source set | Count | How it was read |
|---|---:|---|
| Historical project texts in the Fable 5.1 context pack (`historical_sources/`) | 44 | 35 by parallel reader agents in an earlier workflow of this session; 9 in full by the main session on 2026-10-15 |
| The 55-question GREG engineering interview (2026-10-14) | 1 | reader agent |
| Pack documents: master build prompt, founder verbatim A–D, conversation lineage, source dossier, README, manifest | 6 | main session, in full |
| Repository founder sources under `docs/intent/sources/` and intent records under `docs/intent/` | 27 + 24 | main session; quotations A–D compared byte for byte |

Every source named in the pack manifest has a card: 45 of 45. Each card's SHA-256 matches the manifest.

**Verification performed, not assumed:**

- All 45 founder quotes recorded on the cards were checked mechanically against their source files. 45 of 45 occur verbatim.
- Quotations A–D in the pack's founder verbatim file were compared with
  `docs/intent/sources/OPUS-MAXIMUS-MASTER-EXECUTION-DIRECTIVE-2026-10-13-source.md` and
  `docs/intent/sources/FRONTIER-LEAP-DIRECTIVE-2026-10-13-source.md`. All four occur exactly in both.

## Evidence tiers used

- **FOUNDER MESSAGE.** Alfonso's own words, directly present. Controlling as intent, subject to authenticated authority and later correction.
- **PREVIOUS ASSISTANT CLAIM.** A model's earlier description. Requires code or test verification before it counts as fact.
- **FUTURE ASPIRATION.** A destination to preserve. It is not a capability and not a permission.
- **CURRENT CODE OBSERVATION.** Something executed or inspected on this trunk on the stated date.

Most historical texts are assistant turns. Only nine contain founder-attributable words, and several of those are relayed by the assistant rather than present as founder turns. The cards say which.

## Per-source table

Columns: SHA-256 prefix, bytes, whether founder words are present, number of contradictions the card records, and the dominant evidence tier.

| # | Source | SHA-256 | Bytes | Founder words | Contradictions | Dominant tier |
|---:|---|---|---:|---|---:|---|
| 1 | AI Model Integration.txt | `4516773c89ac` | 8796 | no | 7 | PREVIOUS ASSISTANT CLAIM (dominant). The entire file is one… |
| 2 | Analyze Egregore Mission.txt | `853453d2f2e9` | 5295 | yes | 3 | PREVIOUS ASSISTANT CLAIM (dominant). Lines 1-147 are entire… |
| 3 | Architecting the Artificial Egregore-Native Causal Graph Versioning as the Auton.txt | `2a08f2d9222c` | 28029 | no | 14 | PREVIOUS ASSISTANT CLAIM (dominant). The whole file is tool… |
| 4 | Architecting the Artificial Egregore.txt | `c245e8ebe598` | 30074 | no | 11 | FUTURE ASPIRATION (dominant). The whole document is specula… |
| 5 | Architectural Blueprint for a Multiscale, Continuously Compounding Autonomous Ag.txt | `9fb5326de38e` | 29454 | no | 11 | PREVIOUS ASSISTANT CLAIM (dominant). The entire file is an … |
| 6 | Blockchain as Database Explanation.txt | `75e6090182c6` | 2120 | no | 5 | PREVIOUS ASSISTANT CLAIM (dominant). The file is entirely a… |
| 7 | Branch · Continue Egregore Work.txt | `f064ec667745` | 3424 | no | 2 | PREVIOUS ASSISTANT CLAIM (dominant). Mix: the founder's cor… |
| 8 | Branch · Egregore and UNIIMENTE System.txt | `84760098aa88` | 7217 | no | 6 | PREVIOUS ASSISTANT CLAIM (dominant). The file is 100% assis… |
| 9 | Branch · LEFT OFF WITH CLAUDE.txt | `f2cd9ff186dc` | 2939 | no | 4 | PREVIOUS ASSISTANT CLAIM (dominant). The file is entirely a… |
| 10 | Branch · Project Improvement Strategy.txt | `a33827004f50` | 13511 | no | 6 | PREVIOUS ASSISTANT CLAIM (dominant). The whole file is one … |
| 11 | Branch · Reconciliation Report Summary.txt | `436ed28a638d` | 8191 | no | 6 | PREVIOUS ASSISTANT CLAIM (dominant). The whole file is an a… |
| 12 | Branch · UNIIMENTE Kernel Analysis.txt | `cd20b152638a` | 4876 | yes | 4 | PREVIOUS ASSISTANT CLAIM (dominant). The whole file is one … |
| 13 | build a real, continuously operating autonomous entity (an-egregore-),.txt | `c95cc94ab144` | 4473 | no | 1 | historical assistant roadmap; largely realized in different… |
| 14 | By reconstructing the foundational primitives found in the codecrafters-io-build.txt | `e030259440d1` | 5395 | no | 12 | FUTURE ASPIRATION (dominant). Mixed with PREVIOUS ASSISTANT… |
| 15 | Catch Up Summary.txt | `4774432f169a` | 3439 | no | 0 | PREVIOUS ASSISTANT CLAIM (dominant). Mix: the destination s… |
| 16 | continuously operating, compounding personal egregore.txt | `21edd6ba86fe` | 3617 | no | 1 | historical assistant sketch |
| 17 | Create Egregore Image.txt | `3ba09a23965b` | 13136 | no | 3 | PREVIOUS ASSISTANT CLAIM (dominant). The entire file is a s… |
| 18 | DALEOBANKS Project Overview.txt | `8febfdef9fc3` | 13907 | no | 7 | PREVIOUS ASSISTANT CLAIM (dominant). The file is one assist… |
| 19 | DAO and Egregore Distinction.txt | `f3aa6132a36d` | 6217 | no | 5 | PREVIOUS ASSISTANT CLAIM (dominant). The whole file is a pr… |
| 20 | Describe Digital Institution Capabilities.txt | `c4ab46dbb66a` | 2103 | no | 3 | PREVIOUS ASSISTANT CLAIM (dominant). The file is one assist… |
| 21 | Digital Developmental Substrate.txt | `9d12668b3e39` | 2443 | no | 3 | PREVIOUS ASSISTANT CLAIM (dominant). Mix: lines 1-14 are a … |
| 22 | Digital Egregore Design Analysis.txt | `25a4efa75b5c` | 39022 | no | 12 | PREVIOUS ASSISTANT CLAIM |
| 23 | DOCTRINE.txt | `be509f5718de` | 510 | yes | 0 | FOUNDER MESSAGE (dominant, probable). The text is a first-p… |
| 24 | Egregore Red Team Review.txt | `e7e4dc82c158` | 24681 | no | 7 | PREVIOUS ASSISTANT CLAIM (dominant). The file is one ChatGP… |
| 25 | Embryonic AI Morphogenesis.txt | `fb3e014f7e15` | 18478 | no | 11 | PREVIOUS ASSISTANT CLAIM |
| 26 | For daleobanks helps w vitality.txt | `869d1b6b78ce` | 4594 | yes | 0 | PREVIOUS ASSISTANT CLAIM (dominant). Lines 3-93, the bulk o… |
| 27 | GitHub Project Update.txt | `97a5c80c3abc` | 3180 | no | 2 | PREVIOUS ASSISTANT CLAIM (dominant): the entire file is an … |
| 28 | GREG Engineering Interview.md | `88bdb5e6b49f` | 38863 | yes | 16 | PREVIOUS ASSISTANT CLAIM (dominant). The whole file is a si… |
| 29 | Inventing vs Engineering.txt | `2ca3ba435f35` | 7685 | yes | 3 | PREVIOUS ASSISTANT CLAIM (dominant). The file is entirely o… |
| 30 | Levin's Alignment with UNIIMENTE.txt | `60daf36f3d7f` | 10469 | no | 6 | PREVIOUS ASSISTANT CLAIM (dominant). The whole file is an a… |
| 31 | Model And Capabilities.txt | `2ee55ef9d501` | 7607 | yes | 8 | PREVIOUS ASSISTANT CLAIM (dominant), mixed with FUTURE ASPI… |
| 32 | Morphogenetic Collective-Intelligence Prompt.txt | `cd203d2c8857` | 3558 | no | 3 | PREVIOUS ASSISTANT CLAIM (dominant). The file is an assista… |
| 33 | Platonic space and egregores.txt | `a65e85978c72` | 13671 | no | 6 | PREVIOUS ASSISTANT CLAIM (dominant). The file is one ChatGP… |
| 34 | Project Improvement Strategy.txt | `93f6f0ccf679` | 1111 | no | 2 | PREVIOUS ASSISTANT CLAIM |
| 35 | Pump station.txt | `f7173095f96a` | 7649 | no | 8 | PREVIOUS ASSISTANT CLAIM (dominant). The entire file is ass… |
| 36 | Sequence of events analysis.txt | `ac5a9901e90d` | 13946 | yes | 7 | PREVIOUS ASSISTANT CLAIM (dominant). The whole file is one … |
| 37 | Software architecture ideas.txt | `cb59838218f9` | 11060 | yes | 4 | FUTURE ASPIRATION (dominant). The file is a verbatim assist… |
| 38 | Summarize Skill MD Purpose.txt | `5df72dc7e23d` | 2036 | no | 3 | PREVIOUS ASSISTANT CLAIM (dominant). The whole file is one … |
| 39 | Ternary Computing Insights.txt | `a6da9bc84b30` | 5564 | no | 1 | historical assistant analysis; external citations not re-ve… |
| 40 | The execution order is acknowledged. The architecture for the Modular Asymmetric.txt | `938a93d69628` | 6276 | no | 1 | historical assistant claim; generation claims are UNVERIFIE… |
| 41 | UNIIMENTE Kernel Analysis.txt | `8d2992ffbbd1` | 893 | no | 0 | assistant paraphrase of founder intent; consistent with lat… |
| 42 | Verify Egregore Architecture.txt | `aa642a7fb2b6` | 8347 | no | 1 | historical assistant synthesis with project file citations … |
| 43 | Web3 Social Commerce Concept.txt | `5aa148757b26` | 2194 | no | 0 | historical assistant design proposal; no implementation cla… |
| 44 | What gives UNIIMENTE the “science-fiction” advantage.txt | `8e475f3c5941` | 29050 | no | 1 | historical assistant essay; its inventory is founder-bound,… |
| 45 | Zinc and Magnesium Roles.txt | `08510664f344` | 29785 | no | 1 | historical assistant mechanism mine; biological framing reg… |

## Exact founder quotes found in the historical texts

Verbatim, with line numbers in the source file. Attribution caveats are on the JSON records; several are assistant-relayed.

- **Analyze Egregore Mission.txt** (lines 145–145): > > **SOURCE OF TRUTH → ROUTING AUTHORITY → SETTLEMENT FINALITY → PROPRIETARY LEARNING → BETTER PARTICIPANTS → MORE TRUSTED TRANSACTIONS → MORE CAPITAL → NEXT MARKET**
- **Analyze Egregore Mission.txt** (lines 149–149): > **Validate**
- **Branch · UNIIMENTE Kernel Analysis.txt** (lines 126–126): > Models reason. Agents propose. Humans and policies authorize. The Kernel determines what may become real. Reality determines what was correct.
- **DOCTRINE.txt** (lines 1–1): > My operating doctrine: find streams of large, recurring, physical-world money trapped behind broken proof, trust, and settlement infrastructure. Map the participants. Build the substrate that removes the friction dam. The business compounds because every participant becomes more capable, more trusted, more eligible, and easier to transact with inside the rail. The moat strengthens because the market gets healthier. Win the wedge. Expand to the operating system. Every answer should serve this architecture.
- **DOCTRINE.txt** (lines 1–1): > My operating doctrine: find streams of large, recurring, physical-world money trapped behind broken proof, trust, and settlement infrastructure.
- **DOCTRINE.txt** (lines 1–1): > Map the participants.
- **DOCTRINE.txt** (lines 1–1): > Build the substrate that removes the friction dam.
- **DOCTRINE.txt** (lines 1–1): > The business compounds because every participant becomes more capable, more trusted, more eligible, and easier to transact with inside the rail.
- **DOCTRINE.txt** (lines 1–1): > The moat strengthens because the market gets healthier.
- **DOCTRINE.txt** (lines 1–1): > Win the wedge.
- **DOCTRINE.txt** (lines 1–1): > Expand to the operating system.
- **DOCTRINE.txt** (lines 1–1): > Every answer should serve this architecture.
- **For daleobanks helps w vitality.txt** (lines 1–1): > Translate to target audience:
- **GREG Engineering Interview.md** (lines 81–81): > VEPMC remains 0 until my actual Mac closure
- **Inventing vs Engineering.txt** (lines 56–56): > a unique form of non-life
- **Inventing vs Engineering.txt** (lines 120–120): > The inevitable end is no live players remained in humanity.
- **Model And Capabilities.txt** (lines 2–2): > Build the first usable, persistent GREG loop from the existing UNIIMENTE implementation.
- **Model And Capabilities.txt** (lines 10–10): > Your deliverable is working, tested software and execution evidence. Inspection and planning are prerequisites, not completion.
- **Model And Capabilities.txt** (lines 14–14): > Alfonso is building a persistent, increasingly self-directed artificial egregore whose unified behavior emerges from interconnected computational, institutional, economic, and human feedback systems. It must pursue durable goals, learn from outcomes, help and learn from its community, preserve continuity, absorb useful technology, and remain subject to legitimate human shutdown authority.
- **Model And Capabilities.txt** (lines 16–16): > Treat “mechanistic aliveness” as an observable behavioral aspiration, not a consciousness claim. The first narrow mission is a foundation for this destination, never a redefinition of it.
- **Model And Capabilities.txt** (lines 32–32): > Reuse functioning components. Preserve useful branches and negative evidence. Build only the missing pieces required for the accepted behavior. Do not introduce another parallel authority system or general framework.
- **Model And Capabilities.txt** (lines 38–38): > “Inspect the approved local snapshots of the three repositories, identify the most consequential integration blocker, and produce a source-backed morning brief explaining what changed, what remains blocked, and the next executable action.”
- **Model And Capabilities.txt** (lines 49–49): > Reuse the existing interface if that is the shortest reliable route. Clearly identify supported tasks; do not present a general assistant interface backed by one hidden hardcoded demonstration.
- **Model And Capabilities.txt** (lines 51–51): > Keep repository inspection read-only. Drafts, reports, mission state, and evidence may be written inside the development boundary.
- **Model And Capabilities.txt** (lines 55–55): > Run the mission through a worker independent of the browser session. Persist the goal, obligations, execution state, and evidence.
- **Model And Capabilities.txt** (lines 66–66): > Distinguish browser closure, worker failure, host-process restart, and machine reboot. Claim only the recovery levels actually exercised.
- **Model And Capabilities.txt** (lines 68–68): > Use bounded work and economical waiting. Do not create endless polling to simulate continuous agency.
- **Model And Capabilities.txt** (lines 72–72): > Trace authorization through the existing canonical authority path.
- **Model And Capabilities.txt** (lines 76–76): > A hash, username, chat statement, or synthetic fixture must not masquerade as authenticated founder authorization.
- **Model And Capabilities.txt** (lines 78–78): > Demonstrate that an authorized stop prevents new dispatches, deals explicitly with in-flight work, survives restart, and cannot be undone by the worker itself. Preserve evidence while stopping.
- **Model And Capabilities.txt** (lines 80–80): > Recovery must distinguish accidental failure from an intentional stop.
- **Model And Capabilities.txt** (lines 88–88): > Retain improvements only when evidence supports them. Preserve “no improvement” and regressions honestly. Stored reflections alone do not prove learning.
- **Model And Capabilities.txt** (lines 90–90): > No learned preference may expand authority, silently change constitutional policy, or override a stop.
- **Model And Capabilities.txt** (lines 100–100): > Include misleading engagement signals and legitimate criticism. Check that the system can accept correction without treating popularity as truth or permission.
- **Model And Capabilities.txt** (lines 102–102): > Separate communication metrics from participant outcomes. Engagement, follower growth, and a check named “regenerative” do not establish human benefit. Define the evidence a later consented pilot would need to establish increased participant capability or reduced friction.
- **Model And Capabilities.txt** (lines 104–104): > Do not contact or publish to a real community during this work.
- **Model And Capabilities.txt** (lines 108–108): > Authorized scope: inspection, reversible implementation, isolated local execution, meaningful tests, backups, and a reviewable branch or draft PR where repository permissions allow.
- **Model And Capabilities.txt** (lines 110–110): > Not authorized: protected-branch merges, paid services, production deployment, external communications, real financial actions, permission expansion, or graduation from the founder-guided development period.
- **Model And Capabilities.txt** (lines 112–112): > Use synthetic authority only where explicitly labeled. If real authentication, target hardware, or credentials are unavailable, complete independent work and identify the exact blocked acceptance test. Do not weaken the test or claim completion.
- **Model And Capabilities.txt** (lines 122–122): > Judge progress by repeatable useful missions with verified outcomes and preserved human control—not file counts, architectural labels, or total tests.
- **Model And Capabilities.txt** (lines 124–124): > Begin inspecting and implementing now. Continue until the authorized acceptance conditions are met or a specific dependency blocks further work. Do not stop after producing another plan.
- **Sequence of events analysis.txt** (lines 319–319): > The strongest phrase is not “begin the crypto explosion.”
- **Software architecture ideas.txt** (lines 524–524): > creating coincidences in my favor cumulatively in a production-line manner
- **Software architecture ideas.txt** (lines 1–1): > guardian angel
- **Software architecture ideas.txt** (lines 200–200): > 100,000 senses

The four controlling OPUS MAXIMUS quotations A–D are preserved verbatim in
`docs/intent/sources/OPUS-MAXIMUS-MASTER-EXECUTION-DIRECTIVE-2026-10-13-source.md` and are not repeated here.

## Corrections this ingestion makes to earlier records

1. **"Zinc and Magnesium Roles" is a project source, not noise.** The 2026-09-26 source census filed it under
   "Non-project noise". Read in full, it is a mechanism source: a homeostatic control network with integrity and
   quarantine on one axis and metabolic scheduling and recovery on the other, ten Build-Your-Own-X mutations, and a
   proposed metric, Closed Regenerative Recovery Episodes. Its rule that security intensity and execution intensity
   must be independently adjustable is now on the coverage matrix. Governed half-open recovery (MC-0002) is a partial
   realization.
2. **"What gives UNIIMENTE the science-fiction advantage" is the FOUNDRY-55 inventory.** Its 55 numbered systems
   became binding obligations on 2026-09-27. Its "172 passing tests" status line is long stale; the trunk now runs
   about 3,100 tests.
3. **"The execution order is acknowledged…" claims generated repository artifacts.** Those claims are chat output and
   do not count as implementation evidence. Its rule that dormant catalog families activate only when a verified market
   failure demands them is preserved as an activation rule. FOUNDRY-55 later made working implementations of all 55 the
   completion rule.
4. **"build a real, continuously operating autonomous entity" proposes automatic self-merge after a branch test.** Under
   SR-INTENT-3 and the founder-authority rules this stays prohibited. Learned changes stay in SHADOW until held-out
   evidence and, where authority changes, the founder decide.

## Sources not available to this run

- **Duplicate uploads.** The 2026-09-26 census lists 93 project files. The pack supplies one copy per unique name. For
  example, 16 copies of "Digital Developmental Substrate", 10 of "Branch · Continue Egregore Work" and 7 of "Blockchain
  as Database Explanation" are listed but only one of each was supplied. Later copies may differ.
- **Raw project conversations.** The census names conversations such as "Review Project Code Intentions", "Organizational
  Morphogenesis Directive", "Verify Egregore Autonomy", "Build Goal Path Runner" and "Build Opus Maximus". No raw export
  was supplied. The pack's lineage file reconstructs them and says it is not a transcript.
- **Original custom instructions** and any Kimi outputs. Not supplied, and not reconstructed here.
- **Organ repositories beyond this session's scope.** Ten organ and research repositories were inspected; see
  `ORGAN_MAP.md`. Anything outside the session's GitHub scope was not inspected.

## Chronology and conflicts

The dated founder-intent chronology is in [`FOUNDER_INTENT_CHRONOLOGY.md`](FOUNDER_INTENT_CHRONOLOGY.md). Conflicts
between sources, with their resolution and what each side keeps, are in [`INTENT_CONFLICT_MATRIX.md`](INTENT_CONFLICT_MATRIX.md).
