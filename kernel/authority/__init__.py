"""Founder approval authority — Hard Rules 2 and 3.

Issues and verifies Ed25519-signed ApprovalRecords bound to an intent
fingerprint. REQUIRE_HUMAN decisions cannot proceed without one.
"""
from .approvals import ApprovalService

__all__ = ["ApprovalService"]
