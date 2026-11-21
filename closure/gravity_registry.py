"""Register the Goal Gravity five-closure checks on the integration registry.

Same pattern as the commercial, advantage and developmental registries: the
core Kernel registry stays constitutionally stable and bounded organs extend
it through explicit registration. Registration verifies; it never activates.
"""
from __future__ import annotations

from closure.framework import ClosureRegistry


def register_goal_gravity_closures(registry: ClosureRegistry) -> ClosureRegistry:
    from egregore.closure import goal_gravity_closures, standing_cognition_closures
    registry.register(standing_cognition_closures())
    registry.register(goal_gravity_closures())
    return registry
