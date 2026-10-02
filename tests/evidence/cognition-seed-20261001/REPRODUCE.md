# Reproduce the scoped development evidence

Repository: dababiyoda/uniimente-kernel. Cognition source commit:
`d17baffa5707e0bb0ee530a45b97b770dea7563e`; phone presentation commit:
`26e44d7`; subsequent inheritance documentation: `af25cff`.
`run-binding.json` and the frozen code digests bind later evidence to these sources.
Python 3.12.16 on Linux x86_64; a fresh disposable development body, not Alfonso's device.

```sh
python -m venv /tmp/greg-seed-venv
/tmp/greg-seed-venv/bin/python -m pip install -r requirements-dev.txt -r requirements-cognition.txt
/tmp/greg-seed-venv/bin/python -m pip check
/tmp/greg-seed-venv/bin/python -m pytest -q
/tmp/greg-seed-venv/bin/python scripts/ci/check_seed_mutants.py /tmp/seed-mutations.json
python scripts/ci/check_authority_singleton.py
python scripts/ci/check_schema_refs.py
/tmp/greg-seed-venv/bin/python -m greg.cognition.seed_evaluation --model YOUR_AUTHORIZED_MODEL --output /tmp/seed-heldout.json
/tmp/greg-seed-venv/bin/python scripts/rehearse_cognition_seed.py /tmp/unused-rehearsal-folder YOUR_AUTHORIZED_MODEL
```

The frozen input suite and evaluator were fixed before evaluation. Do not run
`--freeze` to make an altered candidate match existing evidence. An intentional
new experiment needs a linked decision and a new freeze. Repeated runs on the
same tasks are not independent problem samples. Runtime numeric proof records
include exact native solver versions; no simulated solver is represented as real.

This session's explicitly authorized free local-model prerequisite used Ollama
0.35.0 (MIT), CPU libraries from its official Linux archive, and Qwen/Qwen3-0.6B-GGUF
revision `23749fefcc72300e3a2ad315e1317431b06b590a`, Q8_0 file SHA-256
`9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031`
(Apache-2.0). Archive digest, exact license hashes and dependency evidence appear
in `dependencies.json`. The temporary test server bound 127.0.0.1:11434 with
`OLLAMA_NO_CLOUD=1`; it was not installed as a service. Its local Modelfile used
`FROM /path/to/verified/Qwen3-0.6B-Q8_0.gguf`, temperature 0, num_ctx 4096, then
`ollama create seed-qwen3:0.6b -f Modelfile`. GREG itself downloads no model or
launches no server. The default recipe does not install future symbolic, graph,
scientific or evolutionary libraries.

Original 9.14 results remain in `heldout-ortools-9.14.json`; the patched environment
uses OR-Tools 9.15.6755 and protobuf 6.33.5. `vulnerability-query.json` retains the
reported advisories; `vulnerability-query-patched.json` records the query after
replacement. This is a database observation, not a security guarantee. The
historical label `full-suite-final.log` belongs to the earlier concurrent 9.14
run: it completed with one self-repair failure; the isolated recheck passed and
`full-suite-patched.log` records the complete green patched run. No failed result
was removed. `phone-console-projection.log` records an incorrect test handler
name; the corrected test and authenticated boundaries passed in the adjoining log.

`cli-rehearsal*/ledger.jsonl` and command logs contain only laboratory identities
and synthetic inputs. Private keys, real founder credentials, downloaded binary
artifacts and model weights are deliberately excluded. The rehearsal kills the
actual `python -m greg run` process, restarts it after signed detachment, checks
revocation, explicitly signs a new laboratory attachment, then reconciles and
checks deduplication. It does not prove cross-service exactly-once effects,
real multi-body continuity or founder-device VEPMC. The independent appraiser
verifies declared mission predicates, not every unstated aspect of usefulness.
