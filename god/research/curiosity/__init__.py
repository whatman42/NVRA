"""Phase 4B — Curiosity engine (anomaly → question, not trade)."""

from .models import AnomalyDescriptor, AnomalyType, CuriosityEvent, Severity
from .detector import AnomalyDetector, default_detectors
from .engine import CuriosityEngine
from .trigger import ResearchTrigger, TriggerResult

__all__ = [
    "AnomalyDescriptor",
    "AnomalyType",
    "CuriosityEvent",
    "Severity",
    "AnomalyDetector",
    "default_detectors",
    "CuriosityEngine",
    "ResearchTrigger",
    "TriggerResult",
]
