from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    PORTAL_REPORT = "portal_report"
    FIELD_REPORT = "field_report"
    OPERATIONAL_CONTEXT = "operational_context"


class ConflictType(str, Enum):
    VEHICLE_ATTRIBUTION = "vehicle_attribution"
    TEMPORAL_MISMATCH = "temporal_mismatch"
    VALUE_MISMATCH = "value_mismatch"


class GapType(str, Enum):
    MISSING_FIELD_ENTRY = "missing_field_entry"
    ODOMETER_INSUFFICIENT = "odometer_insufficient"
    RESOLUTION_EVIDENCE_REQUIRED = "resolution_evidence_required"


class ItemStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


class ResolutionType(str, Enum):
    DIRECT_EVIDENCE = "direct_evidence"
    OPERATIONAL_CONTEXT = "operational_context"
    INFERENCE = "inference"
    ESTIMATE = "estimate"
    HUMAN_JUDGEMENT = "human_judgement"


class ResolutionStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"


class Readiness(str, Enum):
    READY = "ready"
    NOT_READY = "not_ready"


@dataclass(frozen=True)
class CandidateMatch:
    portal_source_id: str
    field_source_id: str
    matched_on: tuple[str, ...]
    differing_fields: tuple[str, ...]
    rule: str


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    source_type: SourceType
    original_record: dict[str, Any]
    provenance: str
    observed_at: str | None = None
    event_time: str | None = None


@dataclass(frozen=True)
class Assertion:
    source_id: str
    value: Any


@dataclass(frozen=True)
class Claim:
    proposition: str
    assertions: tuple[Assertion, ...]


@dataclass(frozen=True)
class Agreement:
    proposition: str
    value: Any
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceConflict:
    conflict_id: str
    conflict_type: ConflictType
    proposition: str
    assertions: tuple[Assertion, ...]
    reason: str
    status: ItemStatus = ItemStatus.OPEN


@dataclass(frozen=True)
class EvidenceGap:
    gap_id: str
    gap_type: GapType
    requirement: str
    downstream_effect: str
    status: ItemStatus = ItemStatus.OPEN


@dataclass(frozen=True)
class Resolution:
    resolution_id: str
    conflict_id: str
    proposition: str
    accepted_value: Any
    resolution_type: ResolutionType
    basis: str
    evidence_source_ids: tuple[str, ...]
    resolved_by: str | None
    status: ResolutionStatus
    resolved_at: str | None = None


@dataclass(frozen=True)
class SupportedFact:
    proposition: str
    value: Any
    basis: str
    source_ids: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceState:
    case_id: str
    sources: tuple[EvidenceSource, ...]
    candidate_matches: tuple[CandidateMatch, ...] = ()
    claims: tuple[Claim, ...] = ()
    agreements: tuple[Agreement, ...] = ()
    conflicts: tuple[EvidenceConflict, ...] = ()
    gaps: tuple[EvidenceGap, ...] = ()
    supported_facts: tuple[SupportedFact, ...] = ()
    unresolved_facts: tuple[str, ...] = ()
    resolutions: tuple[Resolution, ...] = ()
    human_judgement_required: bool = False
    downstream_readiness: Readiness = Readiness.NOT_READY
    accepted_downstream_state: dict[str, Any] | None = None
    provenance_trail: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return _enum_values(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "EvidenceState":
        return cls(
            case_id=payload["case_id"],
            sources=tuple(
                EvidenceSource(
                    source_id=item["source_id"],
                    source_type=SourceType(item["source_type"]),
                    original_record=item["original_record"],
                    provenance=item["provenance"],
                    observed_at=item.get("observed_at"),
                    event_time=item.get("event_time"),
                )
                for item in payload["sources"]
            ),
            candidate_matches=tuple(
                CandidateMatch(
                    portal_source_id=item["portal_source_id"],
                    field_source_id=item["field_source_id"],
                    matched_on=tuple(item["matched_on"]),
                    differing_fields=tuple(item["differing_fields"]),
                    rule=item["rule"],
                )
                for item in payload.get("candidate_matches", [])
            ),
            claims=tuple(
                Claim(item["proposition"], tuple(Assertion(**a) for a in item["assertions"]))
                for item in payload.get("claims", [])
            ),
            agreements=tuple(
                Agreement(item["proposition"], item["value"], tuple(item["source_ids"]))
                for item in payload.get("agreements", [])
            ),
            conflicts=tuple(
                EvidenceConflict(
                    conflict_id=item["conflict_id"],
                    conflict_type=ConflictType(item["conflict_type"]),
                    proposition=item["proposition"],
                    assertions=tuple(Assertion(**a) for a in item["assertions"]),
                    reason=item["reason"],
                    status=ItemStatus(item["status"]),
                )
                for item in payload.get("conflicts", [])
            ),
            gaps=tuple(
                EvidenceGap(
                    gap_id=item["gap_id"],
                    gap_type=GapType(item["gap_type"]),
                    requirement=item["requirement"],
                    downstream_effect=item["downstream_effect"],
                    status=ItemStatus(item["status"]),
                )
                for item in payload.get("gaps", [])
            ),
            supported_facts=tuple(
                SupportedFact(item["proposition"], item["value"], item["basis"], tuple(item["source_ids"]))
                for item in payload.get("supported_facts", [])
            ),
            unresolved_facts=tuple(payload.get("unresolved_facts", [])),
            resolutions=tuple(
                Resolution(
                    resolution_id=item["resolution_id"],
                    conflict_id=item["conflict_id"],
                    proposition=item["proposition"],
                    accepted_value=item["accepted_value"],
                    resolution_type=ResolutionType(item["resolution_type"]),
                    basis=item["basis"],
                    evidence_source_ids=tuple(item["evidence_source_ids"]),
                    resolved_by=item.get("resolved_by"),
                    status=ResolutionStatus(item["status"]),
                    resolved_at=item.get("resolved_at"),
                )
                for item in payload.get("resolutions", [])
            ),
            human_judgement_required=payload.get("human_judgement_required", False),
            downstream_readiness=Readiness(payload["downstream_readiness"]),
            accepted_downstream_state=payload.get("accepted_downstream_state"),
            provenance_trail=tuple(payload.get("provenance_trail", [])),
        )


def _enum_values(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _enum_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_enum_values(item) for item in value]
    return value
