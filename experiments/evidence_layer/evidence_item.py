"""Domain-neutral first-class evidence items.

This module is additive. It does not replace or alter the existing EvidenceState
types or reconciliation rules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .canonical import canonical_json_text, canonical_sha256


class EvidenceItemState(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONFLICTING = "CONFLICTING"
    MISSING = "MISSING"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"
    HUMAN_JUDGEMENT_REQUIRED = "HUMAN_JUDGEMENT_REQUIRED"


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    item_id: str
    case_id: str
    state: EvidenceItemState
    proposition: str
    source_ids: tuple[str, ...]
    evidence_basis: str
    relevant_temporal_boundary: str
    uncertainty: str
    evidence_to_resolve_uncertainty: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", EvidenceItemState(self.state))
        if isinstance(self.source_ids, (str, bytes, bytearray)):
            raise ValueError("source_ids must be a sequence of strings, not a string")
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        for field_name in (
            "item_id",
            "case_id",
            "proposition",
            "evidence_basis",
            "relevant_temporal_boundary",
            "uncertainty",
        ):
            _require_text(field_name, getattr(self, field_name))
        if any(not isinstance(source_id, str) or not source_id.strip() for source_id in self.source_ids):
            raise ValueError("source_ids must contain only non-empty strings")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("source_ids must not contain duplicates")
        if self.evidence_to_resolve_uncertainty is not None:
            _require_text(
                "evidence_to_resolve_uncertainty",
                self.evidence_to_resolve_uncertainty,
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "evidence_basis": self.evidence_basis,
            "evidence_to_resolve_uncertainty": self.evidence_to_resolve_uncertainty,
            "item_id": self.item_id,
            "proposition": self.proposition,
            "relevant_temporal_boundary": self.relevant_temporal_boundary,
            "source_ids": list(self.source_ids),
            "state": self.state.value,
            "uncertainty": self.uncertainty,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidenceItem":
        return cls(
            item_id=payload["item_id"],
            case_id=payload["case_id"],
            state=EvidenceItemState(payload["state"]),
            proposition=payload["proposition"],
            source_ids=tuple(payload.get("source_ids", ())),
            evidence_basis=payload["evidence_basis"],
            relevant_temporal_boundary=payload["relevant_temporal_boundary"],
            uncertainty=payload["uncertainty"],
            evidence_to_resolve_uncertainty=payload.get("evidence_to_resolve_uncertainty"),
        )

    def to_canonical_json(self) -> str:
        return canonical_json_text(self.to_dict())

    @classmethod
    def from_canonical_json(cls, serialized: str | bytes) -> "EvidenceItem":
        payload = json.loads(serialized)
        if not isinstance(payload, dict):
            raise ValueError("EvidenceItem JSON must contain an object")
        return cls.from_dict(payload)

    @property
    def sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def _require_text(field_name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
