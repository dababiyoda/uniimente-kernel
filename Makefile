# Developer entry points. Each target runs exactly what CI runs; see
# .github/workflows/canonical-ci.yml for the authoritative job list.
PYTHON ?= python

.PHONY: help install test unit verify contracts authority sealed lint ci

help:  ## List targets
	@grep -E "^[a-z-]+:.*## " $(MAKEFILE_LIST) | awk -F ":.*## " "{printf \"  %-10s %s\\n\", \$$1, \$$2}"

install:  ## Install development dependencies
	$(PYTHON) -m pip install -r requirements-dev.txt

test:  ## Full unit + integration suite (needs full git history)
	$(PYTHON) -m pytest -q

unit:  ## Unit suite only
	$(PYTHON) -m pytest -q tests/unit

verify:  ## Institutional verifier V1-V5 (records a run under verifier/runs/)
	$(PYTHON) verifier/v2/verify.py

contracts:  ## CI job 2: every contract schema reference resolves
	$(PYTHON) scripts/ci/check_schema_refs.py

authority:  ## CI job 3: one Constitution, Gate and authority registry
	$(PYTHON) scripts/ci/check_authority_singleton.py

sealed:  ## CI job 4: developmental work has zero external effects
	$(PYTHON) scripts/ci/check_sealed_developmental.py

lint:  ## Correctness lint (ruff; config in pyproject.toml). Not yet a CI job.
	ruff check .

ci: test contracts authority sealed verify  ## Every local check CI job 1-4 runs
