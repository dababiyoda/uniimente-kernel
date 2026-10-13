"""Local open-weight models as detachable proposer parts.

Wraps ``egregore.local_model.LocalDraftProposer`` (loopback-only OpenAI
protocol: Ollama, llama.cpp, vLLM, LocalAI) as a ``PartSpec`` plus callable
for ``PartsBoard.register``. A newer or larger local model is a new part:
register it, shadow it against the current one, then bind it under a Gate
grant, or roll back.

Everything about the endpoint and the proposal scope comes from the local
adapter: hosted or credential-bearing URLs and redirects are refused, the
model supplies only draft objective and text, scope is a fixed internal
draft, and confidence is zero. Hosted models are deliberately not offered
here (see ``docs/OPEN_SOURCE_STACK.md``); enabling one needs its own
reviewed change.
"""
from __future__ import annotations

from typing import Any, Callable

from .contracts import require_text
from .local_model import LocalDraftProposer, LocalModelClient, LocalModelConfig
from .parts import PartSpec


def local_draft_part(
    *,
    role: str = "local_drafter",
    config: LocalModelConfig | None = None,
    client: Any = None,
    provenance: str = "egregore.local_model.LocalDraftProposer",
    model_digest: str | None = None,
) -> tuple[PartSpec, Callable]:
    """Build a (spec, proposer) pair for a local model in ``proposer:<role>``.

    ``client`` defaults to a ``LocalModelClient`` for ``config`` (or the
    LLM_BASE_URL/LLM_MODEL environment); tests may inject a fake client
    exposing ``config`` and ``complete(system, user)``. ``model_digest`` is the
    sha256 of the model manifest or weights when known (e.g. from the local
    server's model listing); it becomes part of the part's identity.
    """
    role = require_text("role", role)
    client = client or LocalModelClient(config)
    model_config = client.config
    proposer = LocalDraftProposer(name=role, client=client)
    spec = PartSpec(
        slot=f"proposer:{role}",
        implementation=f"local-openai-protocol:{model_config.model}",
        version=f"{model_config.base_url}|max_tokens={model_config.max_tokens}",
        provenance=require_text("provenance", provenance),
        open_weights=True,
        notes="loopback only; fixed internal draft scope; confidence 0",
        model_digest=model_digest,
    )
    return spec, proposer
