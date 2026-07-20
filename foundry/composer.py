"""Deterministic Asymmetric Advantage Foundry Composer.

The Composer selects the minimum currently relevant arsenal, resolves
technology dependencies, binds available Capability Genomes, and emits a
reversible Advantage Genome. It never deploys, spends, publishes, or contacts
external parties. Those effects belong exclusively to the Consequence Gate.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Mapping

from capabilities.genome import Genome