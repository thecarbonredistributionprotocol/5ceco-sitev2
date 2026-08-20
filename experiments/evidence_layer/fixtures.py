from __future__ import annotations

from dataclasses import dataclass

from .model import EvidenceSource, Resolution, ResolutionStatus, ResolutionType, SourceType


@dataclass(frozen=True)
class SyntheticCase:
    case_id: str
    description: str
    portal: EvidenceSource
    field: EvidenceSource | None
    context_sources: tuple[EvidenceSource, ...] = ()
    resolution: Resolution | None = None
    require_monthly_kmpl: bool = False


def matching_records() -> SyntheticCase:
    portal, field = _pair("matching", "TRUCK-17", "TRUCK-17")
    return SyntheticCase("matching", "Matching records with no discrepancy", portal, field)


def wrong_vehicle_unresolved() -> SyntheticCase:
    portal, field = _pair("wrong-vehicle-open", "VEHICLE-X", "VEHICLE-Y")
    context = EvidenceSource(
        source_id="context:breakdown-log",
        source_type=SourceType.OPERATIONAL_CONTEXT,
        original_record={"vehicle_out_of_service": "VEHICLE-X", "backup_vehicle": "VEHICLE-Y"},
        provenance="Synthetic breakdown log supplied for prototype testing",
        observed_at="2026-07-31T17:00:00Z",
    )
    proposed = Resolution(
        resolution_id="resolution:wrong-vehicle-proposed",
        conflict_id="wrong-vehicle-open:vehicle_number",
        proposition="vehicle_number",
        accepted_value="VEHICLE-Y",
        resolution_type=ResolutionType.OPERATIONAL_CONTEXT,
        basis="Breakdown log identifies Y as the backup vehicle; operator acceptance is still required.",
        evidence_source_ids=(context.source_id,),
        resolved_by=None,
        status=ResolutionStatus.PROPOSED,
    )
    return SyntheticCase(
        "wrong-vehicle-open",
        "Wrong-vehicle attribution with a proposed but unaccepted correction",
        portal,
        field,
        (context,),
        proposed,
    )


def wrong_vehicle_resolved() -> SyntheticCase:
    open_case = wrong_vehicle_unresolved()
    accepted = Resolution(
        resolution_id="resolution:wrong-vehicle-accepted",
        conflict_id="wrong-vehicle-resolved:vehicle_number",
        proposition="vehicle_number",
        accepted_value="VEHICLE-Y",
        resolution_type=ResolutionType.HUMAN_JUDGEMENT,
        basis="Operator reviewed the breakdown log and confirmed Y received the fuel.",
        evidence_source_ids=(open_case.context_sources[0].source_id,),
        resolved_by="synthetic-operator-01",
        status=ResolutionStatus.ACCEPTED,
        resolved_at="2026-08-04T09:30:00Z",
    )
    portal, field = _pair("wrong-vehicle-resolved", "VEHICLE-X", "VEHICLE-Y")
    return SyntheticCase(
        "wrong-vehicle-resolved",
        "Wrong-vehicle attribution explicitly resolved to Y",
        portal,
        field,
        open_case.context_sources,
        accepted,
    )


def temporal_mismatch_linked() -> SyntheticCase:
    portal, field = _pair("temporal-linked", "TRUCK-17", "TRUCK-17")
    portal = EvidenceSource(
        source_id=portal.source_id,
        source_type=portal.source_type,
        original_record={**portal.original_record, "transaction_id": "TX-731-44", "posting_time": "2026-08-03"},
        provenance=portal.provenance,
        observed_at="2026-08-03",
        event_time="2026-07-31",
    )
    field = EvidenceSource(
        source_id=field.source_id,
        source_type=field.source_type,
        original_record={**field.original_record, "portal_transaction_id": "TX-731-44"},
        provenance=field.provenance,
        event_time="2026-07-31",
    )
    return SyntheticCase(
        "temporal-linked",
        "July 31 physical event linked to an August 3 payment posting",
        portal,
        field,
    )


def missing_field_entry() -> SyntheticCase:
    portal, _ = _pair("missing-field", "TRUCK-17", "TRUCK-17")
    return SyntheticCase(
        "missing-field",
        "Portal transaction with no corresponding Field Report entry",
        portal,
        None,
    )


def odometer_insufficient() -> SyntheticCase:
    portal, field = _pair("odometer-gap", "TRUCK-17", "TRUCK-17")
    field = EvidenceSource(
        source_id=field.source_id,
        source_type=field.source_type,
        original_record={**field.original_record, "opening_odometer": 125_400, "closing_odometer": None},
        provenance=field.provenance,
        event_time=field.event_time,
    )
    return SyntheticCase(
        "odometer-gap",
        "Monthly KMPL requested without a credible closing odometer",
        portal,
        field,
        require_monthly_kmpl=True,
    )


def practitioner_cases() -> tuple[SyntheticCase, ...]:
    return (
        wrong_vehicle_unresolved(),
        wrong_vehicle_resolved(),
        temporal_mismatch_linked(),
        missing_field_entry(),
        odometer_insufficient(),
    )


def all_cases() -> tuple[SyntheticCase, ...]:
    return (matching_records(), *practitioner_cases())


def _pair(prefix: str, portal_vehicle: str, field_vehicle: str) -> tuple[EvidenceSource, EvidenceSource]:
    common = {
        "quantity": 82.5,
        "station": "SYNTHETIC-STATION-04",
        "total_amount": 136.95,
    }
    portal = EvidenceSource(
        source_id=f"portal:{prefix}",
        source_type=SourceType.PORTAL_REPORT,
        original_record={
            **common,
            "vehicle_number": portal_vehicle,
            "unit_price": 1.66,
            "odometer_entered": 125_630,
            "event_time": "2026-07-31",
        },
        provenance="Synthetic Fuel Portal Report row",
        observed_at="2026-07-31",
        event_time="2026-07-31",
    )
    field = EvidenceSource(
        source_id=f"field:{prefix}",
        source_type=SourceType.FIELD_REPORT,
        original_record={
            **common,
            "vehicle_number": field_vehicle,
            "previous_odometer": 125_400,
            "current_odometer": 125_630,
            "event_time": "2026-07-31",
        },
        provenance="Synthetic Field Report row",
        event_time="2026-07-31",
    )
    return portal, field
