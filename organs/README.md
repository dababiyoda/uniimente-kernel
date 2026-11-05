# organs/

Organ manifests (`<organ>.manifest.yaml`), validated against
`contracts/organ-manifest.schema.json`. `linker/` loads every
`*.manifest.yaml` here and resolves cross-organ edges, reporting unresolved
fields instead of inventing them. GREG's runtime organ bridge is
`greg/organs.py` / `greg/organ_bridge.py`. Discovery is never authority.
