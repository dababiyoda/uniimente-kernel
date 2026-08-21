"""Reality Aperture ISSUER distribution.

Ships separately from `uniimente-aperture-client`. Installing the client does
NOT install this package, so an organ cannot import a signer even by accident.

    from aperture_issuer import AuthorityIssuer, Ed25519SigningProvider
"""
from .signing import (SigningProvider, Ed25519SigningProvider,
                      SigningUnavailable)
from .issuer import (AuthorityIssuer, Principal, Proposal, ApprovalRecord,
                     BudgetOffice, PolicyRefusal, ApprovalRequired,
                     ScopeRefusal, UnknownEntity, BudgetRefusal,
                     CONSEQUENCE_ORDER)
from .revocation_authority import RevocationAuthority

__all__ = ["SigningProvider", "Ed25519SigningProvider", "SigningUnavailable",
           "AuthorityIssuer", "Principal", "Proposal", "ApprovalRecord",
           "BudgetOffice", "PolicyRefusal", "ApprovalRequired", "ScopeRefusal",
           "UnknownEntity", "BudgetRefusal", "CONSEQUENCE_ORDER",
           "RevocationAuthority"]
