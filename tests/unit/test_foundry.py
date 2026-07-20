"""Asymmetric Advantage Foundry v0 acceptance tests.

The Foundry composes plans only. It must select a bounded technology set,
resolve dependencies, preserve reversibility, expose implementation gaps, and
refuse authority or budget mismatches before any external effect is possible.
"""

import pytest

from capabilities.genome import AuthorityEnvelope, CapabilityGenome
from foundry import ARSENAL, AdvantageRequest, EvidenceExperiment, FoundryComposer, FoundryRefused


def _request(**kw):
    base = dict(
        market_failure="buyers cannot verify delivery before settlement",
        beneficiaries=("buyer", "provider"),
        payer="buyer",
        control_surfaces=("proof", "settlement"),
        desired_metrics=("dispute_rate",),
        max_budget_usd=25.0,
        evidence_refs=("sha256:" + "a" * 64,),
        kill_conditions=("dispute rate does not improve after one bounded cycle",),
    )
    base.update(kw)
    return AdvantageRequest(**base)


def _capability(**kw):
    base = dict(
        name="site.publish",
        version="1.0.0",
        description="publish an approved site artifact",
        interface={"inputs": {"artifact": "str"}, "outputs": {"receipt": "str"}},
        contracts=["event", "outcome"],
        authority=AuthorityEnvelope(
            max_consequence_class="external_contact",
            budget_ceiling_usd=10.0,
            requires_human=False,
        ),
        acceptance_tests=["publishes only the authorized artifact"],
        failure_modes=["destination unavailable"],
        recovery_path="requeue through the durable workflow",
    )
    base.update(kw)
    return CapabilityGenome(**base)


class TestArsenal:
    def test_registry_is_exactly_55_unique_valid_entries(self):
        assert set(ARSENAL) == set(range(1, 56))
        assert len({spec.name for spec in ARSENAL.values()}) == 55
        assert all(spec.validate() == [] for spec in ARSENAL.values())


class TestComposition:
    def test_minimum_feasible_selection_is_deterministic(self):
        composer = FoundryComposer()
        first = composer.compose(_request())
        second = composer.compose(_request())
        assert first.selected_technology_ids == second.selected_technology_ids
        assert first.request_hash == second.request_hash
        assert first.selected_technology_ids == (4, 5, 6)
        assert first.verify_id()
        assert second.verify_id()

    def test_dependencies_precede_dependants_and_detach_in_reverse(self):
        genome = FoundryComposer().compose(_request(requested_technology_ids=(30,)))
        selected = genome.selected_technology_ids
        assert selected.index(4) < selected.index(5) < selected.index(6) < selected.index(30)
        attached = [step.technology_id for step in genome.attachment_plan]
        detached = [step.technology_id for step in genome.detachment_plan]
        assert attached == list(selected)
        assert detached == list(reversed(selected))

    def test_prohibited_required_dependency_fails_closed(self):
        with pytest.raises(FoundryRefused, match="prohibited"):
            FoundryComposer().compose(
                _request(
                    control_surfaces=("payment",),
                    requested_technology_ids=(38,),
                    prohibited_technology_ids=(30,),
                )
            )

    def test_financial_composition_requires_human(self):
        genome = FoundryComposer().compose(
            _request(control_surfaces=("payment",), desired_metrics=("time_to_payment",))
        )
        assert genome.consequence_class == "financial"
        assert genome.requires_human is True
        payment_step = next(step for step in genome.attachment_plan if step.technology_id == 38)
        assert payment_step.requires_human is True

    def test_target_technology_is_exposed_as_deployment_blocker(self):
        genome = FoundryComposer().compose(
            _request(control_surfaces=("continuity",), desired_metrics=("state_continuity",))
        )
        assert 46 in genome.selected_technology_ids
        assert genome.implementation_status[46] == "target"
        assert any("deployment_blocker: technology 46" in note for note in genome.notes)

    def test_composer_emits_plan_not_execution_authority(self):
        genome = FoundryComposer().compose(_request())
        assert "plan_only: no infrastructure or external effect has been created" in genome.notes
        assert "execution_requires_consequence_gate" in genome.notes
        assert genome.legal_principal == "alfonso_lopez"
        assert all(step.reversible for step in genome.attachment_plan)


class TestCapabilityBinding:
    def test_registered_capability_can_bind_inside_its_envelope(self):
        capability = _capability()
        composer = FoundryComposer(
            capability_genomes={"site.publish@1.0.0": capability},
            technology_capabilities={31: ("site.publish@1.0.0",)},
        )
        genome = composer.compose(
            _request(control_surfaces=("customer",), desired_metrics=("conversion_rate",))
        )
        assert 31 in genome.selected_technology_ids
        assert genome.selected_capability_genomes == ("site.publish@1.0.0",)

    def test_missing_capability_binding_is_refused(self):
        composer = FoundryComposer(
            technology_capabilities={31: ("site.publish@1.0.0",)},
        )
        with pytest.raises(FoundryRefused, match="unregistered capability"):
            composer.compose(
                _request(control_surfaces=("customer",), desired_metrics=("conversion_rate",))
            )

    def test_capability_below_required_consequence_is_refused(self):
        capability = _capability(
            authority=AuthorityEnvelope(
                max_consequence_class="internal_write",
                budget_ceiling_usd=10.0,
                requires_human=False,
            )
        )
        composer = FoundryComposer(
            capability_genomes={"site.publish@1.0.0": capability},
            technology_capabilities={31: ("site.publish@1.0.0",)},
        )
        with pytest.raises(FoundryRefused, match="authority envelope"):
            composer.compose(
                _request(control_surfaces=("customer",), desired_metrics=("conversion_rate",))
            )


class TestExperimentBounds:
    def test_experiment_above_request_budget_is_refused(self):
        experiment = EvidenceExperiment(
            hypothesis="proof reduces disputes",
            prediction="dispute rate falls",
            metric="dispute_rate",
            baseline=0.2,
            threshold=0.1,
            direction="lte",
            budget_usd=30.0,
            observation_window="7 days",
            reversible=True,
            rollback="detach the proof workflow",
            success_next_decision="retain review",
            failure_next_decision="kill",
        )
        with pytest.raises(FoundryRefused, match="exceeds request ceiling"):
            FoundryComposer().compose(_request(max_budget_usd=25.0), experiment=experiment)

    def test_irreversible_experiment_is_refused(self):
        experiment = EvidenceExperiment(
            hypothesis="proof reduces disputes",
            prediction="dispute rate falls",
            metric="dispute_rate",
            baseline=0.2,
            threshold=0.1,
            direction="lte",
            budget_usd=0.0,
            observation_window="7 days",
            reversible=False,
            rollback="none",
            success_next_decision="retain review",
            failure_next_decision="kill",
        )
        with pytest.raises(FoundryRefused, match="irreversible experiments"):
            FoundryComposer().compose(_request(), experiment=experiment)
