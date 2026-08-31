"""Bundled thin EA artifact specs and test fixtures.

Real compiled .ex4/.ex5 are platform-specific; for Linux CI we use
deterministic fixture bytes registered via ArtifactRegistry.
"""

from .registry import ArtifactRegistry, get_default_registry

__all__ = ["ArtifactRegistry", "get_default_registry"]
