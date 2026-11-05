# organs/

Organ manifests (`<organ>.manifest.yaml`), validated against
`contracts/organ-manifest.schema.json`. Each declares an organ's identity,
capabilities, events consumed and produced, and prohibited actions.

`linker/` loads every `*.manifest.yaml` here and resolves cross-organ edges,
reporting unresolved fields instead of inventing them. Discovery is never
authority: nothing in a manifest grants permission to act.
