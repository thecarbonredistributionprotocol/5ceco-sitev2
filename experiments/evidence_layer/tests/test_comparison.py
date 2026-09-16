from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.evidence_layer.canonical import canonical_sha256
from experiments.evidence_layer.comparison import (
    ArtifactMutationError,
    ArtifactRole,
    ComparisonClassification,
    ComparisonItem,
    ComparisonRun,
    ComparisonValidationError,
    ImmutableJsonArtifact,
    ProvenanceReference,
    build_human_comparison,
    write_new_comparison_output,
)


class ComparisonHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.gigacarbon_path = root / "gigacarbon.json"
        self.practitioner_path = root / "practitioner.json"
        self.gigacarbon_path.write_text(
            json.dumps({"cases": [{"case_id": "case-01", "findings": ["gc-01"]}]}, indent=2) + "\n"
        )
        self.practitioner_path.write_text(
            json.dumps({"cases": [{"case_id": "case-01", "findings": ["pr-01"]}]}, indent=2) + "\n"
        )
        self.gigacarbon = ImmutableJsonArtifact.from_path(
            self.gigacarbon_path,
            ArtifactRole.GIGACARBON_OUTPUT,
        )
        self.practitioner = ImmutableJsonArtifact.from_path(
            self.practitioner_path,
            ArtifactRole.PRACTITIONER_AUDIT_READ,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _items(self):
        classifications = tuple(ComparisonClassification)
        items = []
        for index, classification in enumerate(classifications, start=1):
            case_id = "case-01" if index <= 2 else "case-02"
            gigacarbon_ids = (
                ()
                if classification == ComparisonClassification.MISSED_MATERIAL_FINDING
                else (f"gc-{index:02d}",)
            )
            items.append(
                ComparisonItem(
                    case_id=case_id,
                    practitioner_finding_id=f"pr-{index:02d}",
                    gigacarbon_finding_ids=gigacarbon_ids,
                    classification=classification,
                    reviewer_rationale=f"Human rationale for {classification.value}.",
                    provenance_references=(
                        ProvenanceReference(
                            artifact_role=ArtifactRole.GIGACARBON_OUTPUT,
                            artifact_sha256=self.gigacarbon.sha256,
                            locator=f"/cases/{case_id}/gigacarbon/{index}",
                            source_id=gigacarbon_ids[0] if gigacarbon_ids else None,
                        ),
                        ProvenanceReference(
                            artifact_role=ArtifactRole.PRACTITIONER_AUDIT_READ,
                            artifact_sha256=self.practitioner.sha256,
                            locator=f"/cases/{case_id}/practitioner/{index}",
                            source_id=f"pr-{index:02d}",
                        ),
                    ),
                    reviewer_identity="reviewer-01",
                    timestamp="2026-09-14T14:00:00Z",
                )
            )
        return tuple(items)

    def _comparison(self, items=None):
        return build_human_comparison(
            run_id="comparison-run-01",
            generated_at="2026-09-14T15:00:00Z",
            gigacarbon_output=self.gigacarbon,
            practitioner_audit_read=self.practitioner,
            items=self._items() if items is None else tuple(items),
        )

    def test_every_comparison_category_is_counted_per_case_and_in_aggregate(self):
        comparison = self._comparison()
        aggregate = comparison.aggregate_scorecard.to_dict()
        self.assertEqual(aggregate["total_comparison_items"], 5)
        self.assertEqual(aggregate["material_findings_reviewed"], 2)
        for classification in ComparisonClassification:
            self.assertEqual(aggregate["classification_counts"][classification.value], 1)
        self.assertEqual([item.case_id for item in comparison.per_case_scorecards], ["case-01", "case-02"])
        self.assertEqual(comparison.per_case_scorecards[0].scorecard.total_comparison_items, 2)
        self.assertEqual(comparison.per_case_scorecards[1].scorecard.total_comparison_items, 3)

    def test_serialization_round_trip_and_hash_are_deterministic(self):
        forward = self._comparison(self._items())
        reverse = self._comparison(reversed(self._items()))
        self.assertEqual(forward.to_canonical_json(), reverse.to_canonical_json())
        self.assertEqual(forward.sha256, reverse.sha256)
        restored = ComparisonRun.from_canonical_json(forward.to_canonical_json())
        self.assertEqual(restored, forward)
        self.assertEqual(restored.sha256, forward.sha256)

    def test_comparison_functions_do_not_modify_source_artifacts(self):
        before = {
            path: (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode)
            for path in (self.gigacarbon_path, self.practitioner_path)
        }
        comparison = self._comparison()
        for path, snapshot in before.items():
            self.assertEqual(
                (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode),
                snapshot,
            )
        with self.assertRaises(TypeError):
            self.gigacarbon.payload["cases"] = ()
        with self.assertRaises(AttributeError):
            self.gigacarbon.payload["cases"].append({})

        with self.assertRaises(ComparisonValidationError):
            write_new_comparison_output(
                self.gigacarbon_path,
                comparison,
                source_artifacts=(self.gigacarbon, self.practitioner),
            )
        self.assertEqual(self.gigacarbon_path.read_bytes(), before[self.gigacarbon_path][0])

        output_path = Path(self.temp_dir.name) / "comparison-output.json"
        written = write_new_comparison_output(
            output_path,
            comparison,
            source_artifacts=(self.gigacarbon, self.practitioner),
        )
        self.assertEqual(ComparisonRun.from_canonical_json(output_path.read_bytes()), comparison)
        self.assertEqual(written.comparison_sha256, comparison.sha256)
        with self.assertRaises(FileExistsError):
            write_new_comparison_output(
                output_path,
                comparison,
                source_artifacts=(self.gigacarbon, self.practitioner),
            )
        for path, snapshot in before.items():
            self.assertEqual(
                (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode),
                snapshot,
            )

    def test_changed_source_is_detected_before_comparison(self):
        self.practitioner_path.write_text('{"changed":true}\n')
        with self.assertRaises(ArtifactMutationError):
            self._comparison()

    def test_malformed_source_is_rejected_when_loaded(self):
        malformed_path = Path(self.temp_dir.name) / "malformed.json"
        malformed_path.write_text("not JSON")
        with self.assertRaises(ComparisonValidationError):
            ImmutableJsonArtifact.from_path(
                malformed_path,
                ArtifactRole.PRACTITIONER_AUDIT_READ,
            )

    def test_direct_artifact_construction_freezes_payload_and_checks_its_hash(self):
        mutable_payload = {"items": []}
        template = ImmutableJsonArtifact.from_payload(
            mutable_payload,
            ArtifactRole.GIGACARBON_OUTPUT,
        )
        artifact = ImmutableJsonArtifact(
            role=template.role,
            sha256=template.sha256,
            canonical_sha256=template.canonical_sha256,
            source_path=None,
            size_bytes=template.size_bytes,
            _payload=mutable_payload,
        )
        mutable_payload["items"].append("later mutation")
        self.assertEqual(artifact.payload["items"], ())

        with self.assertRaises(ComparisonValidationError):
            ImmutableJsonArtifact(
                role=template.role,
                sha256=template.sha256,
                canonical_sha256="0" * 64,
                source_path=None,
                size_bytes=template.size_bytes,
                _payload={"items": []},
            )

    def test_provenance_hash_must_match_loaded_input(self):
        item = self._items()[0]
        bad_reference = ProvenanceReference(
            artifact_role=ArtifactRole.GIGACARBON_OUTPUT,
            artifact_sha256="0" * 64,
            locator="/wrong/hash",
        )
        bad_item = ComparisonItem(
            case_id=item.case_id,
            practitioner_finding_id=item.practitioner_finding_id,
            gigacarbon_finding_ids=item.gigacarbon_finding_ids,
            classification=item.classification,
            reviewer_rationale=item.reviewer_rationale,
            provenance_references=(bad_reference,),
            reviewer_identity=item.reviewer_identity,
            timestamp=item.timestamp,
        )
        with self.assertRaises(ComparisonValidationError):
            self._comparison((bad_item,))

    def test_tampered_serialized_output_is_rejected(self):
        comparison = self._comparison()
        output = json.loads(comparison.to_canonical_json())
        output["comparison"]["items"][0]["reviewer_rationale"] = "Changed after hashing."
        with self.assertRaises(ComparisonValidationError):
            ComparisonRun.from_canonical_json(json.dumps(output))

    def test_rehashed_output_with_mismatched_provenance_is_rejected(self):
        output = json.loads(self._comparison().to_canonical_json())
        output["comparison"]["items"][0]["provenance_references"][0][
            "artifact_sha256"
        ] = "0" * 64
        output["comparison_sha256"] = canonical_sha256(output["comparison"])
        with self.assertRaises(ComparisonValidationError):
            ComparisonRun.from_canonical_json(json.dumps(output))

    def test_duplicate_practitioner_finding_ids_are_rejected_per_case(self):
        item = self._items()[0]
        with self.assertRaises(ComparisonValidationError):
            self._comparison((item, item))

    def test_output_writer_requires_the_exact_source_artifacts(self):
        comparison = self._comparison()
        output_path = Path(self.temp_dir.name) / "comparison-output.json"
        with self.assertRaises(ComparisonValidationError):
            write_new_comparison_output(
                output_path,
                comparison,
                source_artifacts=(self.gigacarbon,),
            )
        self.assertFalse(output_path.exists())

    def test_reviewer_and_run_timestamps_must_be_timezone_aware(self):
        item = self._items()[0]
        with self.assertRaises(ComparisonValidationError):
            ComparisonItem(
                case_id=item.case_id,
                practitioner_finding_id=item.practitioner_finding_id,
                gigacarbon_finding_ids=item.gigacarbon_finding_ids,
                classification=item.classification,
                reviewer_rationale=item.reviewer_rationale,
                provenance_references=item.provenance_references,
                reviewer_identity=item.reviewer_identity,
                timestamp="2026-09-14T14:00:00",
            )
        with self.assertRaises(ComparisonValidationError):
            build_human_comparison(
                run_id="comparison-run-02",
                generated_at="2026-09-14T15:00:00",
                gigacarbon_output=self.gigacarbon,
                practitioner_audit_read=self.practitioner,
                items=(item,),
            )


if __name__ == "__main__":
    unittest.main()
