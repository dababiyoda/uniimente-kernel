"""Governance contracts.

RegenerativeImpactRecord enforces a closed five-account model (natural, built,
human, social, financial): an incomplete account set is ambiguous and fails
closed (Hard Rule 4). SwarmContract caps maximum_agents at 16.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from .base import KernelModel
from .action import ConsequenceClass

FIVE_ACCOUNTS = ("natural", "built", "human", "social", "financial")


class RegenerativeImpactRecord(KernelModel):
    subject_id: str
    accounts: dict[str, float]  # exactly the five accounts
    debt: float
    blocking: bool

    @field_validator("accounts")
    @classmethod
    def _exactly_five_accounts(cls, v):
        if set(v.keys()) != set(FIVE_ACCOUNTS):
            raise ValueError(f"accounts must contain exactly the five accounts {FIVE_ACCOUNTS}")
        return v


class IncidentRecord(KernelModel):
    severity: Literal["S1", "S2", "S3", "S4"]
    description: str
    evidence_ids: list[str]
    containment: str
    new_detection_rule: str | None = None


class OrganCharter(KernelModel):
    organ_id: str
    objective: str
    owner: str
    capabilities: list[str]
    budget: dict[str, float]
    autonomy_ceiling: Literal["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]
    lifespan_days: int
    kill_condition: str


class BusinessGenome(KernelModel):
    recurring_failure: str
    affected_person: str
    buyer: str
    budget_owner: str
    existing_workaround: str
    urgency: str
    offer: str
    evidence: list[str]
    distribution: str
    acquisition: str
    conversion: str
    fulfillment: str
    retention: str
    revenue_model: str
    contribution_margin: float
    working_capital: float
    legal_constraints: list[str]
    required_capabilities: list[str]
    required_automations: list[str]
    regenerative_effect: dict[str, Any]
    capital_ceiling: float
    advancement_gate: str
    kill_condition: str


class SwarmContract(KernelModel):
    objective: str
    owner: str
    legal_principal: str
    deliverable: str
    required_evidence: list[str]
    maximum_agents: int = Field(ge=1, le=16)
    role_types: list[str]
    communication_schemas: list[str]
    allowed_tools: list[str]
    allowed_data: list[str]
    total_budget: dict[str, float]
    consequence_ceiling: ConsequenceClass
    lifespan_hours: int
    success_condition: str
    failure_condition: str
    shutdown: str
