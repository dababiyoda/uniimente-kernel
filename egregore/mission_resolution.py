"""Compatibility import. Canonical owner: routing.mission_selector.

Expiry trigger: all consumers migrate their imports. Removal condition: no
remaining imports of egregore.mission_resolution. Original implementation is
preserved at 6b2547298eb2ef7c452bb5699f9e59a562b7d4d9.
"""
from routing.mission_selector import (
    EVIDENCE_MATURITY, RESOLUTION_CLASSES, MissionResolution, MissionResolutionError,
    MissionResolutionRouter, ResolutionCandidate, ResolutionClass,
)
