# observability

Operational observability: metrics, logs, traces (OpenTelemetry-style). Deliberately separate from provenance: observability answers is it healthy, provenance answers why was this allowed. Build target for Phase 4.

Phase 2 note: the heartbeat supervisor was extracted from DALEOBANKS and now ships inside the SDK package as `uniimente_kernel.heartbeat`; the package is its canonical home so organs can import it via pip.
