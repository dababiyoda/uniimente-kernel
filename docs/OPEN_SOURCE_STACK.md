# Egregore: open-source-first AI and software

Development candidate, 2026-09-30. Applies across UNIIMENTE Kernel,
DALEOBANKS, WealthMachineIntelligence and attached tools. This records the current
request as a software-selection directive, not a runtime grant or deployment.

## Founder direction and observable effect

Exact current chat: “For my entire egregore project use open source ai models for him  really look in GitHub for free opensource projects with lots of stars like the awesome repo and others high value free opensource repos, and use them to ur advantage to get all that would be paid to be free”.

Literal targets: use locally served freely licensed models; reuse mature free
software before paying or building commodity replacements; avoid automatic billing.
“Egregore” refers to the existing institution and its components, not a new model,
framework or biological imitation. This advances INTENT-0030.

Success: normal draft generation reaches a loopback model, existing API keys do not
change that routing, local failure never calls a paid service, drafts still pass
existing contracts/guards, and license/resource information is reviewable.

## What the source inspection found

| Component | Current mechanism | Change / boundary |
| --- | --- | --- |
| Kernel `egregore/runtime.py` | Injected proposer/evaluator functions; no hardcoded paid LLM | Add `egregore.local_model.LocalDraftProposer` using local /v1 chat; existing scheduler/runtime remains owner |
| DALEOBANKS `services/llm_adapter.py` | GPT-4o-mini hardcoded; requires OpenAI client key | Default Ollama + Qwen3.5-4B; configurable model/server; existing templates remain fallback |
| DALEOBANKS `services/llm_harness.py` | Existing OpenAI key selected paid route before Ollama | Explicit provider choice; default local even with an existing key |
| DALEOBANKS semantic memory | Free hash vectors; paid embedding modes optional | Add local Nomic embeddings, hash fallback, model-aware vector tags; auto never selects billing from a key |
| WMI current main | Deterministic/heuristic assessment, plus explicitly labeled simulated market code | No paid LLM calls discovered; preserve these checks instead of inserting an unnecessary model or claiming trained forecasting |
| God's Eye tool | Optional paid HUD summaries and proprietary realtime WebRTC | Separate local HUD candidate; realtime voice needs a distinct STT → local model/tools → TTS integration |
| RailScout | Only agent instructions and README on main | No executable model call to migrate yet |
| Other historical/research organs | Not exhaustively migrated in this candidate | Apply this selection rule to each active call site; don't claim whole-project operational completion |

Sources are default branches inspected on this date, not every historical branch.
The attached cloud environment failed; a separate MarcoPolo shell cloned public
sources for testing. No credentials, live model service, or target hardware was
provided. Mock protocol tests do not prove inference quality or deployment.

## Minimal local model setup

Use [Ollama](https://github.com/ollama/ollama) (MIT) as the first server, with
[Qwen/Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B) (model-card license:
Apache 2.0). The [Ollama model tag](https://ollama.com/library/qwen3.5:4b) and
[OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility) were checked.

Set `OLLAMA_NO_CLOUD=1` in the **server's** environment, then start Ollama. Setting
it only in an organ's .env does not reconfigure an already running Ollama service.

```bash
OLLAMA_NO_CLOUD=1 ollama serve
# In another terminal:
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
export LLM_PROVIDER=ollama
export LLM_BASE_URL=http://127.0.0.1:11434/v1
export LLM_MODEL=qwen3.5:4b
```

Model downloads are separate from activation. Bind the server to loopback. Local
adapters refuse hosted/credential-bearing URLs and redirects; no paid fallback is
configured. Remote self-hosting/container networking needs an explicit reviewed
configuration change rather than relabeling a hosted service as free.

For Kernel source-checkout use:

```python
from egregore.local_model import LocalDraftProposer
drafter = LocalDraftProposer()
# Supply {drafter.name: drafter} to the EXISTING StandingCognitionRuntime
# constructor alongside the existing ledger, required evaluators and resources.
```

The existing runtime charges a model-call slot before invoking the proposer.
Output is a fixed-scope internal draft; model output cannot set authority, target,
capability, cost, evidence references or confidence. Confidence is deliberately
zero; verification must come from existing evaluators. No scheduler is launched.
The current boundary-only wheel does not package egregore; use a source checkout,
not a claim that this adds a production packaged runtime.

For DALEOBANKS copy its .env.example and keep LIVE=false. It uses the open-source
OpenAI SDK solely as a compatible client to a local URL. Explicit legacy
`LLM_PROVIDER=openai` remains preserved for historical compatibility; that mode
is paid and is outside the requested free default. Offline fixtures can use
`LLM_PROVIDER=template` and `EMBEDDINGS_PROVIDER=hash`.

## Hardware and model choice

Start with 4B quantized weights. A machine with roughly 8–16 GB total RAM and
several GB of free disk is a plausible starting point, but context, OS memory,
quantization and multimodal use change requirements. CPU operation is possible and
may be slow. This is a planning estimate, not a measured requirement or guarantee.

[Qwen3.8-27B](https://github.com/QwenLM/Qwen3.8) is a newer official candidate for a
larger machine; review the exact weight license and runtime support, then benchmark
before changing defaults. Stars alone do not make a model fit available memory.
Use llama.cpp for direct GGUF/CPU control, or vLLM for an existing GPU/high
concurrency installation. All serve the same /v1 interface; don't install every
server or run every model at once.

## GitHub research and reuse map

Exact popularity snapshot and maintenance dates are in
[repositories-2026-09-30.json](open-source/repositories-2026-09-30.json).

| Repository | Stars observed | License inspected / qualification |
| --- | ---: | --- |
| [sindresorhus/awesome](https://github.com/sindresorhus/awesome) | 512,621 | CC0-1.0 |
| [awesome-selfhosted/awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) | 322,816 | CC-BY-SA-3.0 |
| [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | 140,306 | Apache-2.0 |
| [ollama/ollama](https://github.com/ollama/ollama) | 181,941 | MIT |
| [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) | 129,939 | MIT |
| [vllm-project/vllm](https://github.com/vllm-project/vllm) | 92,981 | Apache-2.0 |
| [mudler/LocalAI](https://github.com/mudler/LocalAI) | 49,336 | MIT |
| [QwenLM/Qwen3](https://github.com/QwenLM/Qwen3) | 27,667 | verify each model card; Qwen3.5-4B Apache-2.0 verified separately |
| [QwenLM/Qwen3.8](https://github.com/QwenLM/Qwen3.8) | 4,203 | Apache-2.0 |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 25,633 | MIT |
| [hexgrad/kokoro](https://github.com/hexgrad/kokoro) | 9,086 | Apache-2.0 |
| [qdrant/qdrant](https://github.com/qdrant/qdrant) | 34,885 | Apache-2.0 |
| [searxng/searxng](https://github.com/searxng/searxng) | 37,790 | AGPL-3.0 |
| [microsoft/playwright](https://github.com/microsoft/playwright) | 96,905 | Apache-2.0 |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 42,502 | MIT |
| [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) | 135,563 | GPL-3.0 |
| [temporalio/temporal](https://github.com/temporalio/temporal) | 23,381 | MIT |
| [activepieces/activepieces](https://github.com/activepieces/activepieces) | 24,801 | MIT community core; enterprise directories excluded |
| [huggingface/sentence-transformers](https://github.com/huggingface/sentence-transformers) | 19,138 | Apache-2.0 |

Use the Awesome repositories as discovery indexes and examples. Their READMEs were
read, including self-hosted and AI categories. Awesome-LLM-Apps includes examples
that call paid Claude/GPT/Gemini/search APIs: an Apache-licensed example does not
make its configured backend free.

| Capability otherwise purchased | Free mechanism to reuse | Adoption status |
| --- | --- | --- |
| Chat, reasoning, structured drafts | Ollama + Qwen; llama.cpp / vLLM / LocalAI alternatives | Local adapters implemented in review candidates |
| Semantic memory / hosted vectors | Nomic local embeddings + current index; Qdrant if scale requires it | Local embedding candidate; Qdrant not installed |
| Speech recognition | faster-whisper + freely licensed Whisper weights | Researched; no microphone/audio adapter installed |
| Speech synthesis | Kokoro + checked voice/model licenses | Researched; no voice service installed |
| Web search API | SearXNG | Researched; upstream engines still impose throttling/terms |
| Browser automation subscriptions | Playwright | Researched; existing access/approval rules still apply |
| Image-generation APIs | ComfyUI + a separately licensed checkpoint | Researched; GPU/model license must be selected |
| Agent workflow SDK | Existing Kernel first; LangGraph only for a missing workflow need | Existing runtime retained; no second authority plane |
| Managed durable scheduling | Existing scheduler first; Temporal self-hosted when justified | Researched; don't add a cluster for a single cron job |
| Zapier-style workflow tooling | Activepieces MIT community core | Researched; enterprise-only directories excluded |

Nomic model reference: [nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5).
Check the exact downloaded weights' license independently from the inference
server's license. Keep model IDs/versions and notices with deployment artifacts.

n8n was checked (206,325 stars) but uses Sustainable Use/enterprise terms, so it
is not an unrestricted open-source default. Current Open WebUI was checked
(153,599 stars) and includes branding restrictions. Both are preserved as research
alternatives rather than silently classified MIT. GPL/AGPL components are genuine
free software with distribution/network-use obligations.

## Costs that software substitution cannot eliminate

Local inference removes model-provider token bills, not electricity, hardware,
disk, backups or rented compute. Free software does not supply paid X API access,
Google photorealistic tiles, exclusive market feeds, SMS delivery, payment
processing or guaranteed free hosting. Use existing keyless globe/public-data
fallbacks, owned data, and lawful free distribution channels where acceptable.
No public-data feed is assumed to have unlimited free quotas or paid-data parity.

Do not route around platform billing or restrictions with automation. A free
search/browser tool still requires access to the data/service it operates.

## Alternatives, review and rollback

Simplest viable mechanism: one existing local OpenAI-compatible server and narrow
adapters. Strongest competing route: vLLM on an already owned GPU; better throughput
but higher operator complexity. Do nothing preserves hardcoded paid chat.
Staged experiment: local drafts and hash/local memory, compare quality before any
activation. A custom LLM/framework was rejected because commodity servers already
supply the protocol. Residual deficit: live target-hardware validation, model-quality
benchmarks, complete realtime speech transport, and any unused-organ call sites.

Five perspectives, recorded by one assistant, not independent review:

- Builder: narrow server adapters preserve existing contracts and reduce vendor cost.
- Adversary: key presence must not enable billing; hostile model output and redirects refuse.
- Operator: model files consume RAM/disk; no automatic installs, server launches or cloud fallback.
- Beneficiary: local prompts can remain on owned hardware; unavailable service must be visible.
- Constitutional reviewer: generated drafts retain no execution authority; original Gate remains owner.

Pass 1: standardize protocol and explicit provider routing; bound inputs, outputs,
timeout and tokens; preserve old implementations and hash memory; keep rollback
independent of model data. A cheap small model can become a quality liability.
Pass 2: check hidden cloud model routing, same-dimension embedding model mixing,
required-evaluator bypass and misleading mock-test claims. Disable Ollama cloud in
the server, distinguish model tags, retain fixed-scope zero-confidence drafts and
explicit evidence limits. No disagreement is erased: full voice parity and large
model quality are still unverified.

Decision: **experiment** in draft review. Falsify the claimed free default if a normal
local request contacts a paid host, a legacy key changes routing, a failure bills a
hosted provider, or a model response expands authority. Stop/revert on those events
or unacceptable quality/resource use. Owner: repository maintainers; Alfonso retains
consequence authority. Attach by supplying the proposer to the existing runtime;
detach by removing that binding. Revert provider configuration to offline
template/hash without deleting ledgers, vectors, evidence or historical code.
