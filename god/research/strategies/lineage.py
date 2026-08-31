"""Lineage helpers — evolutionary genealogy queries."""

from __future__ import annotations

from typing import Optional

from .models import ResearchStrategy
from .registry import StrategyRegistry


def parent_of(registry: StrategyRegistry, strategy: ResearchStrategy) -> Optional[ResearchStrategy]:
    if not strategy.parent_strategy_id:
        return None
    return registry.get(strategy.parent_strategy_id, strategy.parent_version)


def ancestors(registry: StrategyRegistry, strategy_id: str) -> list[ResearchStrategy]:
    return registry.genealogy(strategy_id)


def descendants(
    registry: StrategyRegistry, strategy_id: str, version: Optional[int] = None
) -> list[ResearchStrategy]:
    return registry.children_of(strategy_id, version)


def full_family_tree(registry: StrategyRegistry, root_id: str) -> dict:
    """Simple nested tree for audit."""
    root = registry.get(root_id)
    if root is None:
        return {}

    def _node(s: ResearchStrategy) -> dict:
        kids = registry.children_of(s.strategy_id, s.version)
        return {
            "identity": s.identity_key(),
            "state": s.lifecycle_state.value,
            "hypothesis_ref": s.hypothesis_ref,
            "children": [_node(c) for c in kids],
        }

    return _node(root)
