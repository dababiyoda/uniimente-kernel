"""Layer 5 acceptance tests: capability genomes.

A capability with an incomplete genome does not instantiate. An authority
envelope that is unbounded is not an envelope. Instantiation requests
must fit INSIDE the registered genome's envelope.
"""
import pytest

from capabilities.genome import (AuthorityEnvelope, CapabilityGenome, GenomeError,
                                 GenomeRegistry)


def _genome(**kw):
    base = dict(name="draft.publish", version="1.0.0",
                description="publish a draft to a sandbox outbox",
                interface={"inputs": {"text": "str"}, "outputs": {"receipt": "str"}},
                contracts=["event", "outcome"],
                authority=AuthorityEnvelope(max_consequence_class="external_contact",
                                            budget_ceiling_usd=25.0, requires_human=False),
                acceptance_tests=["publishes exactly the authorized payload"],
                failure_modes=["outbox unavailable", "payload rejected"],
                recovery_path="requeue via durable workflow")
    base.update(kw)
    return CapabilityGenome(**base)


class TestGenomeContract:
    def test_complete_genome_registers(self):
        reg = GenomeRegistry()
        reg.register(_genome())
        assert reg.get("draft.publish", "1.0.0") is not None

    def test_incomplete_genome_refused(self):
        reg = GenomeRegistry()
        with pytest.raises(GenomeError):
            reg.register(_genome(acceptance_tests=[]))
        with pytest.raises(GenomeError):
            reg.register(_genome(interface={"inputs": {}}))   # no outputs
        with pytest.raises(GenomeError):
            reg.register(_genome(contracts=["not-a-contract"]))

    def test_unbounded_authority_refused(self):
        reg = GenomeRegistry()
        with pytest.raises(GenomeError, match="require a human"):
            reg.register(_genome(authority=AuthorityEnvelope(
                max_consequence_class="irreversible", budget_ceiling_usd=100.0,
                requires_human=False)))

    def test_uniimente_never_operator(self):
        reg = GenomeRegistry()
        with pytest.raises(GenomeError, match="UNIIMENTE"):
            reg.register(_genome(legal_operator="UNIIMENTE"))


class TestInstantiationBounds:
    def test_request_inside_envelope_allowed(self):
        reg = GenomeRegistry()
        reg.register(_genome())
        ok, _ = reg.may_instantiate("draft.publish", "1.0.0",
                                    requested_class="internal_write", requested_budget_usd=10.0)
        assert ok

    def test_class_above_envelope_refused(self):
        reg = GenomeRegistry()
        reg.register(_genome())
        ok, msg = reg.may_instantiate("draft.publish", "1.0.0",
                                      requested_class="financial", requested_budget_usd=0.0)
        assert not ok and "exceeds genome envelope" in msg

    def test_budget_above_ceiling_refused(self):
        reg = GenomeRegistry()
        reg.register(_genome())
        ok, msg = reg.may_instantiate("draft.publish", "1.0.0",
                                      requested_class="read_only", requested_budget_usd=30.0)
        assert not ok and "exceeds ceiling" in msg

    def test_unregistered_capability_never_instantiates(self):
        ok, msg = GenomeRegistry().may_instantiate("ghost", "9.9",
                                                   requested_class="read_only",
                                                   requested_budget_usd=0.0)
        assert not ok and "no genome" in msg
