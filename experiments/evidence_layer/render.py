from __future__ import annotations

from .model import EvidenceState, ResolutionStatus, SourceType


def human_summary(state: EvidenceState) -> str:
    portal = next(item for item in state.sources if item.source_type == SourceType.PORTAL_REPORT)
    field = next((item for item in state.sources if item.source_type == SourceType.FIELD_REPORT), None)
    proposed = [item for item in state.resolutions if item.status == ResolutionStatus.PROPOSED]
    accepted = [item for item in state.resolutions if item.status == ResolutionStatus.ACCEPTED]
    lines = [
        f"CASE: {state.case_id}",
        f"1. Portal says: {_compact(portal.original_record)}",
        f"2. Field says: {_compact(field.original_record) if field else 'No corresponding Field Report entry.'}",
        "3. Conflicts / missing: " + (
            "; ".join([f"{item.proposition}: {item.reason}" for item in state.conflicts if item.status.value == "open"] + [item.requirement for item in state.gaps])
            or "None."
        ),
        "4. Established without judgement: " + (
            "; ".join(f"{item.proposition}={item.value!r}" for item in state.supported_facts if not item.basis.startswith("accepted"))
            or "No cross-source fact beyond source presence."
        ),
        "5. Additional context required: " + (
            "; ".join(item.requirement for item in state.gaps)
            or ("An explicit resolution of the open conflict." if any(item.status.value == "open" for item in state.conflicts) else "None.")
        ),
        "6. Proposed correction: " + ("; ".join(f"{item.proposition}={item.accepted_value!r}" for item in proposed) or "None."),
        "7. Correction evidence: " + (
            "; ".join(f"{item.basis} [{', '.join(item.evidence_source_ids)}]" for item in (*proposed, *accepted)) or "None."
        ),
        f"8. Human judgement required: {'yes' if state.human_judgement_required else 'no'}"
        + (f"; unresolved: {', '.join(state.unresolved_facts)}" if state.unresolved_facts else ""),
        f"9. Downstream readiness: {state.downstream_readiness.value}"
        + (f"; accepted state: {_compact(state.accepted_downstream_state)}" if state.accepted_downstream_state else ""),
    ]
    return "\n".join(lines)


def _compact(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, dict):
        return ", ".join(f"{key}={item!r}" for key, item in value.items())
    return repr(value)
