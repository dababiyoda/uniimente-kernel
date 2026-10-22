"""Compatibility name for the legacy ``cognition/1`` seed path.

Both frontier lineages moved the original ``greg/cognition.py`` into this package under different
names: ``seed_path`` (#155/#158, the canonical ``cognition.seed.solve`` registration) and
``seed_compat`` (#156/#159, the schema-routed dispatcher in ``greg.cognition.solve``). The
convergence keeps ONE implementation, :mod:`greg.cognition.seed_path`; this module name is bound to
that same module object, so ``greg.cognition.seed_compat`` and ``greg.cognition.seed_path`` are one
module (one set of globals, one ``_worker``, one policy). No second implementation, registry entry,
policy or authority lives here.
"""
import sys as _sys

from . import seed_path as _implementation

_sys.modules[__name__] = _implementation
