"""Deterministic evidence-state prototype for operational records."""

from .model import EvidenceState, Resolution
from .reconcile import reconcile

__all__ = ["EvidenceState", "Resolution", "reconcile"]
