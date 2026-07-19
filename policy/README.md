# policy

Policy engine. Evaluates compiled UCL at proposal time and commit time. Deny by default. Returns structured refusal reasons. Build target for Phase 2.

Phase 2 note: the first two policy modules were extracted from DALEOBANKS and now ship inside the SDK package — `uniimente_kernel.constitution_check` (constitution guard) and `uniimente_kernel.approval_queue` (operator command channel). They lived here briefly; the package is their canonical home so organs can import them via pip.
