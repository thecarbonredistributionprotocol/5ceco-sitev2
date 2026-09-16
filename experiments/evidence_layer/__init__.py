"""Deterministic evidence-state primitives for operational records."""

from .comparison import ComparisonItem, ComparisonRun, build_human_comparison
from .evidence_item import EvidenceItem, EvidenceItemState
from .model import EvidenceState, Resolution
from .reconcile import reconcile

__all__ = [
    "ComparisonItem",
    "ComparisonRun",
    "EvidenceItem",
    "EvidenceItemState",
    "EvidenceState",
    "Resolution",
    "build_human_comparison",
    "reconcile",
]
