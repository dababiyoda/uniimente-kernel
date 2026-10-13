# Open-source research and business draft assembly

Founder direction, 2026-09-30: use Awesome and trusted, popular open-source
projects to give Egregore useful interconnected business capabilities.

This implements one reusable line: source discovery → retained citations →
local hypothesis → valid opportunity packet → existing WMI assessment →
existing DALEOBANKS media drafts → pending review bundle. It also accepts local
document excerpts and reports completed bundles with DuckDB. It reuses the
Kernel's Loom, ratification, durable workflow checkpoints, and evidence ledger.

Software installation and successful tests do not grant permission to publish,
contact prospects, spend money, or qualify a Foundry opportunity. The CLI's
sandbox preview of supplied data works without a production ratification record.
Production execution consumes existing, hash-bound Loom ratification. A live
SearXNG query is external contact, and additionally consumes an exact pre-existing
grant through the canonical ConsequenceGate, with a witness and receipt.

## Sources actually examined

GitHub metadata and source READMEs were checked on 2026-09-30. Stars help discover
established projects; licenses, active maintenance and mechanism fit determine
selection. List entries can be stale: Awesome Selfhosted still labels Open WebUI
BSD, while the repository's current branding restrictions were identified in
the earlier research. The upstream license controls.

| Repository | Stars at check | License / scope | Application |
| --- | ---: | --- | --- |
| [Awesome](https://github.com/sindresorhus/awesome) | 512,631 | CC0 | Discovery across existing lists; not installed as a runtime |
| [Awesome Selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) | 322,823 | CC BY-SA 3.0 list | Located SearXNG, Ollama, LocalAI and Activepieces |
| [Awesome LLM Apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | 140,317 | Apache 2.0 examples | Examined local RAG example: retrieve evidence before local generation; many other examples require paid APIs |
| [SearXNG](https://github.com/searxng/searxng) | 37,793 | AGPL 3.0 | Bounded loopback JSON search; no search API subscription |
| [Ollama](https://github.com/ollama/ollama) | 181,941, earlier check | MIT server | Local OpenAI-compatible inference, cloud disabled in Compose |
| [Qwen3.5-4B model](https://huggingface.co/Qwen/Qwen3.5-4B) | Not a GitHub star metric | Apache 2.0 model card checked | Baseline freely licensed local model; no model downloaded by this change |
| [DuckDB](https://github.com/duckdb/duckdb) | 41,819 | MIT | Optional local reporting over canonical completed checkpoints |
| [Playwright](https://github.com/microsoft/playwright) | 96,909 | Apache 2.0 | Evaluated; browser capture remains a separate future adapter |
| [Docling](https://github.com/docling-project/docling) | 68,205 | MIT code; inspect model licenses separately | Evaluated; PDF/OCR ingestion remains a separate future adapter |

The [larger selection catalogue](OPEN_SOURCE_STACK.md) covers inference,
embeddings, vector search, workflow automation, speech, image generation and
alternatives. Only integrated stages above are claimed as working code.
Qdrant/Agno/another agent framework were unnecessary for a small source set:
existing semantic memory and the Kernel already cover orchestration.
The causal mechanism adopted from local RAG is evidence-bound generation;
the tutorial's custom-license Llama model was replaced with the checked Qwen
model, and its framework was not copied.

## Repeatable offline preview

Use clean source checkouts beside the Kernel checkout. Python 3.11+ on Linux/macOS is required by the existing POSIX ledger. Use WSL on Windows.
This uses synthetic search data, a deterministic preview hypothesis, the real
WMI evaluator and the real DALEOBANKS refinery. It calls no model or search service.

~~~bash
git clone https://github.com/dababiyoda/uniimente-kernel.git
git clone https://github.com/dababiyoda/WealthMachineIntelligence.git
git clone https://github.com/dababiyoda/DALEOBANKS.git
cd uniimente-kernel
python -m venv .venv-research
. .venv-research/bin/activate
python -m pip install -r requirements-research-line.txt
python -m foundry.research_line --mode preview \
  --job examples/research-line/job.json \
  --wmi-source ../WealthMachineIntelligence --dale-source ../DALEOBANKS \
  --fixture-results examples/research-line/search-fixture.json \
  --template-analysis --out research-preview.json
~~~

Use a fresh export path on subsequent previews; the CLI refuses to overwrite
an existing artifact. The preview uses an isolated in-memory sandbox ledger and
labels its output synthetic. It never writes production ratification.
Consumer computations run in temporary child processes with no inherited API
keys, bridge credentials, hosted database URL, proxy configuration, or live mode.
The installed dotenv version honors PYTHON_DOTENV_DISABLED. WMI uses its existing
graph-only fallback with minimal dependencies; any available SQL database is
explicitly in memory. The consumer decision entries are retained in the workflow
state; the canonical parent ledger remains the workflow checkpoint owner.
These processes are isolation for configuration and module names, not a security
sandbox for arbitrary untrusted Python. Only trusted source checkouts are allowed.

The checked consumer revisions in CI are:
WMI ec82b8027d987c865dc123215afb53d20916908f and
DALEOBANKS a8341ba81622dbd1180583bc6660fa1e7ed707b8.
Local planning records actual clean checkout revisions and refuses changes
before consumer computation.

## Local search and model services

The included Compose file binds services to loopback, persists downloaded
weights, and sets OLLAMA_NO_CLOUD=1 inside the model server. SearXNG's official
JSON format setting was checked against docs/dev/search_api.rst. Its image digest
was verified at GHCR on this date for amd64, arm64 and arm/v7. Ollama's v0.35.0
release tag was checked; it is a version tag, not an immutable digest.
This is a CPU baseline; GPU configuration depends on the target machine.
Docker deployment and real model quality are not established by mocked HTTP tests.

~~~bash
docker compose -f deploy/research-line/compose.yaml up -d
docker compose -f deploy/research-line/compose.yaml exec ollama ollama pull qwen3.5:4b
python -m foundry.research_line --mode preview \
  --job examples/research-line/job.json \
  --wmi-source ../WealthMachineIntelligence --dale-source ../DALEOBANKS \
  --fixture-results examples/research-line/search-fixture.json \
  --out local-model-synthetic-preview.json
~~~

That command previews real local inference over synthetic source observations;
it does not issue a SearXNG query. Replace --fixture-results with --observations
/path/to/research-observations.json to use operator-supplied observations instead.
Both files contain a list of SearXNG-shaped title/url/content objects. Supplied
observations remain unverified; their content is bound into the workflow pattern.

SearXNG forwards search queries to its configured external search engines.
It removes a paid search API dependency; it does not make searches offline or
guarantee engine availability. Do not send confidential business material in
search queries. Local document excerpts can be supplied in the job JSON without
a remote document service: each requires exactly title and text (4,000 characters
maximum). Search snippets are observations, not full-page captures, verified
facts, paid commitments or buyer interviews.

Live search uses the Python runtime API with the already configured canonical gate,
not a self-authorizing CLI. ResearchLine.propose_search prepares a request using an
existing actor/legal principal and upstream-reviewed evidence references/confidence.
It issues no grant. The existing authorization path must approve the exact query,
loopback endpoint, source limit and disclosure. Pass gate, proposal, grant and any
existing gate approver into line.workflow; the gate must use the workflow ledger.
Loom also requires its existing human step approval for this external_contact step.
Missing, revoked, changed or mismatched authority refuses before an HTTP request.
The receipt and witness IDs are linked in the review bundle. A disclosed query cannot
be recalled; compensation retains an audit note rather than claiming to undo it.
The CLI's execute/resume path requires --observations, so it never creates its own
gate/passport/grant stack or silently forwards a query. The runtime adapter enables
the interconnected live path while preserving the existing owner of authority.

The JSON job supports query, audience, buyer_type, risk_flags and documents.
Leave buyer_type empty unless supplied by the operator; models cannot fill it.
Confidence is fixed at zero; WMI's modeled scores/ROI are preserved as recommendations
and are not customer evidence. Search warnings and unknowns remain in the bundle.
No runtime model failure falls back to a paid provider.

## Governed execution and recovery

Plan with --mode plan to print the canonical WorkflowPattern and its content hash.
It binds the job, service settings, fixture data, adapter source hashes and both
consumer revisions. A human/operator decision through the existing Loom Ratifier
must already exist on the canonical ledger before --mode execute can weave it.
The CLI deliberately has no command that invents a founder approval record.

Use --observations, --ledger, --anchor and a unique --workflow-id with execute. The anchor must
match the existing constitution-bound ledger; no invented anchor is a production
substitute. Resume the same job/configuration/revisions with --mode resume.
The line refuses a changed pattern, revoked ratification, mismatched ratifier
ledger, or workflow identity rebound to another pattern.

A stop before a step resumes from its retained cursor. Started but unacknowledged
steps fail with reconciliation_required; do not blindly retry a possible effect.
All records, including failures, remain on the existing evidence ledger.
Withdrawal marks the derived review bundle withdrawn without deleting history.
Removing the invocation disables this line; stopping Compose stops its services.
Existing templates and previously approved local-AI routes remain available.

Optional reporting reads and verifies the same ledger without writing it:

~~~bash
python -m foundry.research_report --ledger /path/to/existing-ledger.jsonl \
  --anchor "the-existing-constitutional-anchor"
~~~

DuckDB counts internal review outputs and verdicts. It does not score business
success or claim revenue. External validation and Foundry qualification still
use the existing contracts, explicit factual intake supplement, approval and
reconciled outcomes. This source-checkout utility is outside the intentionally
small uniimente-kernel-boundaries wheel.

## Verification and practical limits

Core tests exercise citation/authority-field rejection, empty evidence,
configuration drift, ratification withdrawal, missing/revoked search grants,
commit-time revalidation with zero HTTP requests, persistent restart, source
deduplication, local HTTP search, redirects, response limits and reporting.
The canonical CI keeps its four original checks and adds one connected-composition
job with pinned real WMI/DALEOBANKS sources. That job exercises actual loopback HTTP
protocols with a fake model/search server plus real consumer calculations, then
exports a synthetic offline preview. These prove composition, not inference quality.

The separate test workspace returned HTTP 504 twice during this change. GitHub
Actions is the executable verification path; current run evidence belongs in
the pull request. No running Docker service, GPU, downloaded model, paid customer
outcome, browser capture, PDF/OCR or full local voice pipeline is claimed.

Software/model token fees on the local route are zero. Hardware, electricity,
hosting, backups and exclusive data can still cost money. See
OPEN_SOURCE_RESEARCH_LINE_REVIEW.md for the effect compilation, alternatives,
review roles, two strengthening passes, owner and kill criteria.
