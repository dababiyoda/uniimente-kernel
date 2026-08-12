"""Aggregate closure registry for the Egregore v1 integration line.

The core Kernel registry remains constitutionally stable. Bounded organs
extend it through explicit registration functions. This module is the
integration verifier entry point, not a second authority path.
"""
from closure.kernel_registry import build_registry as build_kernel_registry
from closure.commercial_registry import register_commercial_closures
from closure.advantage_registry import register_advantage_closures
from closure.developmental_registry import register_developmental_closures
from closure.nervous_system_registry import register_nervous_system_closures


def build_registry():
    registry = build_kernel_registry()
    register_commercial_closures(registry)
    register_advantage_closures(registry)
    register_developmental_closures(registry)
    register_nervous_system_closures(registry)
    return registry
