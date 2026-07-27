"""Single Bottleneck Metric: founder intent -> decision -> action -> evidence -> outcome.

Read-only audit of completion claims. Holds no authority; repairs nothing.
"""

from .chain import (
    COMPLETION_STATE,
    LINKS,
    GoalTrace,
    TraceabilityWalker,
    UnauthorizedEffect,
    UnresolvedLink,
)
from .metric import MetricReport, single_bottleneck_metric

__all__ = [
    "COMPLETION_STATE", "LINKS", "GoalTrace", "TraceabilityWalker",
    "UnauthorizedEffect", "UnresolvedLink", "MetricReport",
    "single_bottleneck_metric",
]
