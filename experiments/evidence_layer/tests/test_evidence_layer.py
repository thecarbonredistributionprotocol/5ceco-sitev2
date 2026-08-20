from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.evidence_layer.fixtures import (
    matching_records,
    missing_field_entry,
    odometer_insufficient,
    temporal_mismatch_linked,
    wrong_vehicle_resolved,
    wrong_vehicle_unresolved,
)
from experiments.evidence_layer.model import ConflictType, EvidenceState, GapType, Readiness, ResolutionStatus
from experiments.evidence_layer.reconcile import reconcile


def run_case(case):
    return reconcile(
        case.case_id,
        case.portal,
        case.field,
        context_sources=case.context_sources,
        resolution=case.resolution,
        require_monthly_kmpl=case.require_monthly_kmpl,
    )


class EvidenceLayerTests(unittest.TestCase):
    def test_matching_records_have_no_discrepancy(self):
        state = run_case(matching_records())
        self.assertEqual(state.conflicts, ())
        self.assertEqual(state.gaps, ())
        self.assertEqual(len(state.candidate_matches), 1)
        self.assertEqual(state.downstream_readiness, Readiness.READY)

    def test_wrong_vehicle_attribution_is_unresolved(self):
        state = run_case(wrong_vehicle_unresolved())
        conflict = next(item for item in state.conflicts if item.conflict_type == ConflictType.VEHICLE_ATTRIBUTION)
        self.assertEqual([item.value for item in conflict.assertions], ["VEHICLE-X", "VEHICLE-Y"])
        self.assertTrue(state.human_judgement_required)
        self.assertEqual(state.downstream_readiness, Readiness.NOT_READY)

    def test_wrong_vehicle_resolution_preserves_original_x_and_accepts_y(self):
        case = wrong_vehicle_resolved()
        portal_before = dict(case.portal.original_record)
        state = run_case(case)
        self.assertEqual(state.sources[0].original_record, portal_before)
        self.assertEqual(state.sources[0].original_record["vehicle_number"], "VEHICLE-X")
        self.assertEqual(state.accepted_downstream_state["vehicle_number"], "VEHICLE-Y")
        self.assertEqual(state.downstream_readiness, Readiness.READY)

    def test_temporal_mismatch_is_linked_as_same_event(self):
        state = run_case(temporal_mismatch_linked())
        self.assertFalse(any(item.conflict_type == ConflictType.TEMPORAL_MISMATCH for item in state.conflicts))
        facts = {item.proposition: item.value for item in state.supported_facts}
        self.assertEqual(facts["physical_event_time"], "2026-07-31")
        self.assertEqual(facts["payment_posting_time"], "2026-08-03")
        self.assertEqual(state.downstream_readiness, Readiness.READY)

    def test_portal_transaction_missing_from_field_is_missingness_not_non_event(self):
        state = run_case(missing_field_entry())
        self.assertTrue(any(item.gap_type == GapType.MISSING_FIELD_ENTRY for item in state.gaps))
        self.assertIn("field_record_presence", state.unresolved_facts)
        self.assertEqual(state.downstream_readiness, Readiness.NOT_READY)

    def test_missing_odometer_evidence_blocks_kmpl(self):
        state = run_case(odometer_insufficient())
        self.assertTrue(any(item.gap_type == GapType.ODOMETER_INSUFFICIENT for item in state.gaps))
        self.assertIn("monthly_kmpl", state.unresolved_facts)
        self.assertEqual(state.downstream_readiness, Readiness.NOT_READY)

    def test_conflicting_evidence_remains_not_ready(self):
        state = run_case(wrong_vehicle_unresolved())
        self.assertIsNone(state.accepted_downstream_state)
        self.assertEqual(state.downstream_readiness, Readiness.NOT_READY)

    def test_explicit_resolution_produces_ready_downstream_state(self):
        state = run_case(wrong_vehicle_resolved())
        self.assertIsNotNone(state.accepted_downstream_state)
        self.assertEqual(state.downstream_readiness, Readiness.READY)

    def test_serialization_round_trip_preserves_provenance_and_observations(self):
        state = run_case(wrong_vehicle_resolved())
        payload = json.loads(json.dumps(state.to_dict()))
        restored = EvidenceState.from_dict(payload)
        self.assertEqual(restored.to_dict(), state.to_dict())
        self.assertEqual(restored.provenance_trail, state.provenance_trail)
        self.assertEqual(restored.sources[0].original_record["vehicle_number"], "VEHICLE-X")

    def test_incomplete_accepted_resolution_is_rejected(self):
        case = wrong_vehicle_unresolved()
        invalid = replace(case.resolution, status=ResolutionStatus.ACCEPTED)
        state = reconcile(
            case.case_id,
            case.portal,
            case.field,
            context_sources=case.context_sources,
            resolution=invalid,
        )
        self.assertTrue(any(item.gap_type == GapType.RESOLUTION_EVIDENCE_REQUIRED for item in state.gaps))
        self.assertEqual(state.downstream_readiness, Readiness.NOT_READY)
        self.assertIsNone(state.accepted_downstream_state)


if __name__ == "__main__":
    unittest.main()
