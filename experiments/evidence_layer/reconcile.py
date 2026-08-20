from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from .model import (
    Agreement,
    Assertion,
    CandidateMatch,
    Claim,
    ConflictType,
    EvidenceConflict,
    EvidenceGap,
    EvidenceSource,
    EvidenceState,
    GapType,
    ItemStatus,
    Readiness,
    Resolution,
    ResolutionStatus,
    SupportedFact,
)


COMPARABLE_FIELDS = ("vehicle_number", "quantity", "station", "total_amount")
MATCH_FIELDS = ("event_time", "quantity", "station", "total_amount")


def identify_candidate_matches(
    portals: tuple[EvidenceSource, ...], fields: tuple[EvidenceSource, ...]
) -> tuple[CandidateMatch, ...]:
    """Return deterministic candidates; this does not declare records equivalent."""
    candidates: list[CandidateMatch] = []
    for portal in portals:
        for field in fields:
            portal_reference = portal.original_record.get("transaction_id")
            field_reference = field.original_record.get("portal_transaction_id")
            shared_reference = portal_reference is not None and portal_reference == field_reference
            matched_on = tuple(
                name
                for name in MATCH_FIELDS
                if _source_value(portal, name) is not None
                and _source_value(portal, name) == _source_value(field, name)
            )
            if shared_reference or len(matched_on) >= 3:
                differing = tuple(
                    name
                    for name in (*COMPARABLE_FIELDS, "event_time")
                    if _source_value(portal, name) is not None
                    and _source_value(field, name) is not None
                    and _source_value(portal, name) != _source_value(field, name)
                )
                candidates.append(
                    CandidateMatch(
                        portal_source_id=portal.source_id,
                        field_source_id=field.source_id,
                        matched_on=("transaction_reference", *matched_on) if shared_reference else matched_on,
                        differing_fields=differing,
                        rule="shared transaction reference" if shared_reference else "at least three exact operational fields",
                    )
                )
    return tuple(candidates)


def reconcile(
    case_id: str,
    portal: EvidenceSource,
    field: EvidenceSource | None,
    *,
    context_sources: tuple[EvidenceSource, ...] = (),
    resolution: Resolution | None = None,
    require_monthly_kmpl: bool = False,
) -> EvidenceState:
    """Build an evidence state without mutating or replacing source observations."""
    sources = tuple(_snapshot(item) for item in (portal, *((field,) if field else ()), *context_sources))
    candidate_matches = identify_candidate_matches((portal,), (field,)) if field else ()
    claims: list[Claim] = []
    agreements: list[Agreement] = []
    conflicts: list[EvidenceConflict] = []
    gaps: list[EvidenceGap] = []
    supported: list[SupportedFact] = []
    unresolved: list[str] = []
    resolutions: list[Resolution] = []

    if field is None:
        gaps.append(
            EvidenceGap(
                gap_id=f"{case_id}:missing-field-entry",
                gap_type=GapType.MISSING_FIELD_ENTRY,
                requirement="A corresponding Field Report entry",
                downstream_effect="Portal presence establishes a transaction was recorded by the portal; field absence does not establish that fuel was not received.",
            )
        )
        supported.append(SupportedFact("portal_transaction_recorded", True, "direct portal evidence", (portal.source_id,)))
        unresolved.append("field_record_presence")
    else:
        for name in COMPARABLE_FIELDS:
            _compare_field(name, portal, field, claims, agreements, conflicts, supported, unresolved, case_id)
        _compare_time(portal, field, claims, agreements, conflicts, supported, unresolved, case_id)

    if require_monthly_kmpl:
        odometer_source = field.original_record if field else {}
        missing = [name for name in ("opening_odometer", "closing_odometer") if odometer_source.get(name) is None]
        if missing or (
            odometer_source.get("opening_odometer") is not None
            and odometer_source.get("closing_odometer") is not None
            and odometer_source["closing_odometer"] < odometer_source["opening_odometer"]
        ):
            gaps.append(
                EvidenceGap(
                    gap_id=f"{case_id}:odometer-insufficient",
                    gap_type=GapType.ODOMETER_INSUFFICIENT,
                    requirement="Credible opening and closing odometers for the calculation period",
                    downstream_effect="Vehicle-level monthly KMPL is not supportable with current evidence.",
                )
            )
            unresolved.append("monthly_kmpl")

    if resolution is not None:
        resolutions.append(resolution)
        matching = next((item for item in conflicts if item.conflict_id == resolution.conflict_id), None)
        evidence_ids = {item.source_id for item in sources}
        can_accept = (
            matching is not None
            and resolution.status == ResolutionStatus.ACCEPTED
            and bool(resolution.resolved_by)
            and bool(resolution.basis.strip())
            and bool(resolution.evidence_source_ids)
            and set(resolution.evidence_source_ids).issubset(evidence_ids)
        )
        if can_accept:
            conflicts = [replace(item, status=ItemStatus.RESOLVED) if item.conflict_id == resolution.conflict_id else item for item in conflicts]
            unresolved = [item for item in unresolved if item != resolution.proposition]
            supported.append(
                SupportedFact(
                    resolution.proposition,
                    resolution.accepted_value,
                    f"accepted {resolution.resolution_type.value}: {resolution.basis}",
                    resolution.evidence_source_ids,
                )
            )
        elif resolution.status == ResolutionStatus.ACCEPTED:
            gaps.append(
                EvidenceGap(
                    gap_id=f"{case_id}:resolution-evidence-required",
                    gap_type=GapType.RESOLUTION_EVIDENCE_REQUIRED,
                    requirement="An accepted resolution must name a resolver, basis, and evidence sources present in this state",
                    downstream_effect="The proposed correction cannot enter the accepted downstream state.",
                )
            )

    open_conflicts = [item for item in conflicts if item.status == ItemStatus.OPEN]
    open_gaps = [item for item in gaps if item.status == ItemStatus.OPEN]
    ready = not open_conflicts and not open_gaps and not unresolved
    accepted = _accepted_state(supported) if ready else None
    human_required = bool(open_conflicts or any(r.status == ResolutionStatus.PROPOSED for r in resolutions))
    provenance = tuple(
        [f"source:{item.source_id}:{item.provenance}" for item in sources]
        + [
            f"resolution:{item.resolution_id}:{item.resolved_by or 'unassigned'}:{item.basis}"
            for item in resolutions
        ]
    )
    return EvidenceState(
        case_id=case_id,
        sources=sources,
        candidate_matches=candidate_matches,
        claims=tuple(claims),
        agreements=tuple(agreements),
        conflicts=tuple(conflicts),
        gaps=tuple(gaps),
        supported_facts=tuple(supported),
        unresolved_facts=tuple(dict.fromkeys(unresolved)),
        resolutions=tuple(resolutions),
        human_judgement_required=human_required,
        downstream_readiness=Readiness.READY if ready else Readiness.NOT_READY,
        accepted_downstream_state=accepted,
        provenance_trail=provenance,
    )


def _compare_field(name, portal, field, claims, agreements, conflicts, supported, unresolved, case_id):
    portal_value = portal.original_record.get(name)
    field_value = field.original_record.get(name)
    assertions = tuple(
        Assertion(source_id, value)
        for source_id, value in ((portal.source_id, portal_value), (field.source_id, field_value))
        if value is not None
    )
    claims.append(Claim(name, assertions))
    if portal_value is None or field_value is None:
        unresolved.append(name)
    elif portal_value == field_value:
        agreements.append(Agreement(name, portal_value, (portal.source_id, field.source_id)))
        supported.append(SupportedFact(name, portal_value, "independent source agreement", (portal.source_id, field.source_id)))
    else:
        conflict_type = ConflictType.VEHICLE_ATTRIBUTION if name == "vehicle_number" else ConflictType.VALUE_MISMATCH
        conflicts.append(
            EvidenceConflict(
                conflict_id=f"{case_id}:{name}",
                conflict_type=conflict_type,
                proposition=name,
                assertions=assertions,
                reason=f"Portal asserts {portal_value!r}; Field asserts {field_value!r}.",
            )
        )
        unresolved.append(name)


def _compare_time(portal, field, claims, agreements, conflicts, supported, unresolved, case_id):
    portal_event = portal.event_time or portal.original_record.get("event_time")
    portal_posting = portal.observed_at or portal.original_record.get("posting_time")
    field_event = field.event_time or field.original_record.get("event_time")
    assertions = (
        Assertion(portal.source_id, {"event_time": portal_event, "posting_time": portal_posting}),
        Assertion(field.source_id, {"event_time": field_event}),
    )
    claims.append(Claim("same_physical_transaction", assertions))
    same_reference = (
        portal.original_record.get("transaction_id") is not None
        and portal.original_record.get("transaction_id") == field.original_record.get("portal_transaction_id")
    )
    if portal_event and field_event and portal_event == field_event and (portal_posting == portal_event or same_reference):
        agreements.append(Agreement("same_physical_transaction", True, (portal.source_id, field.source_id)))
        supported.append(
            SupportedFact(
                "physical_event_time",
                portal_event,
                "matching event time" + (" and cross-source transaction reference" if same_reference else ""),
                (portal.source_id, field.source_id),
            )
        )
        if portal_posting and portal_posting != portal_event:
            supported.append(SupportedFact("payment_posting_time", portal_posting, "direct portal evidence", (portal.source_id,)))
    else:
        conflicts.append(
            EvidenceConflict(
                conflict_id=f"{case_id}:transaction-time",
                conflict_type=ConflictType.TEMPORAL_MISMATCH,
                proposition="same_physical_transaction",
                assertions=assertions,
                reason="Event and posting dates do not establish the same physical transaction without a shared reference or other linking evidence.",
            )
        )
        unresolved.append("same_physical_transaction")


def _accepted_state(facts: list[SupportedFact]) -> dict:
    return {item.proposition: deepcopy(item.value) for item in facts}


def _snapshot(source: EvidenceSource) -> EvidenceSource:
    return replace(source, original_record=deepcopy(source.original_record))


def _source_value(source: EvidenceSource, name: str):
    if name == "event_time":
        return source.event_time or source.original_record.get(name)
    return source.original_record.get(name)
