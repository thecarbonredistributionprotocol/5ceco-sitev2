from __future__ import annotations

import json
import unittest

from experiments.evidence_layer.evidence_item import EvidenceItem, EvidenceItemState
from experiments.evidence_layer.fixtures import matching_records
from experiments.evidence_layer.reconcile import reconcile


class EvidenceItemTests(unittest.TestCase):
    def test_every_generic_state_round_trips_deterministically(self):
        for state in EvidenceItemState:
            with self.subTest(state=state.value):
                item = EvidenceItem(
                    item_id=f"item:{state.value.lower()}",
                    case_id="case:generic-01",
                    state=state,
                    proposition="generic proposition",
                    source_ids=["source:01", "source:02"],
                    evidence_basis="Evidence supplied by the referenced sources.",
                    relevant_temporal_boundary="2026-09-14T12:00:00Z",
                    uncertainty="The records do not settle the remaining question.",
                    evidence_to_resolve_uncertainty="An additional source addressing the proposition.",
                )
                restored = EvidenceItem.from_canonical_json(item.to_canonical_json())
                self.assertEqual(restored, item)
                self.assertEqual(restored.sha256, item.sha256)
                self.assertEqual(json.loads(item.to_canonical_json()), item.to_dict())

    def test_resolution_evidence_is_optional_and_zero_sources_are_supported(self):
        item = EvidenceItem(
            item_id="item:missing",
            case_id="case:generic-02",
            state=EvidenceItemState.MISSING,
            proposition="A source needed to assess the proposition",
            source_ids=(),
            evidence_basis="No relevant source is present in the bounded evidence set.",
            relevant_temporal_boundary="Evidence-set freeze boundary",
            uncertainty="Absence is not proof of non-occurrence.",
        )
        self.assertIsNone(item.evidence_to_resolve_uncertainty)
        self.assertEqual(item.source_ids, ())

    def test_duplicate_source_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceItem(
                item_id="item:duplicate",
                case_id="case:generic-03",
                state=EvidenceItemState.SUPPORTED,
                proposition="A proposition",
                source_ids=("source:01", "source:01"),
                evidence_basis="A basis",
                relevant_temporal_boundary="A boundary",
                uncertainty="An uncertainty",
            )

    def test_source_ids_reject_a_bare_string(self):
        with self.assertRaises(ValueError):
            EvidenceItem(
                item_id="item:invalid-sources",
                case_id="case:generic-04",
                state=EvidenceItemState.SUPPORTED,
                proposition="A proposition",
                source_ids="source:01",
                evidence_basis="A basis",
                relevant_temporal_boundary="A boundary",
                uncertainty="An uncertainty",
            )

    def test_existing_evidence_state_serialization_shape_is_unchanged(self):
        case = matching_records()
        state = reconcile(case.case_id, case.portal, case.field)
        self.assertNotIn("evidence_items", state.to_dict())
        self.assertEqual(state.to_dict()["case_id"], "matching")


if __name__ == "__main__":
    unittest.main()
