"""Deterministic extreme-market scenario definitions for paper validation."""
from dataclasses import dataclass
@dataclass(frozen=True)
class Scenario: name:str; price_shock:float=0.0; volume_multiplier:float=1.0; correlation:float=0.0
SCENARIOS=(Scenario('flash_crash',-0.25,0.5,0.9),Scenario('gap_down',-0.15,0.7,0.8),Scenario('liquidity_drought',-0.02,0.05,0.5),Scenario('systemic_correlation',-0.08,0.8,0.99))
