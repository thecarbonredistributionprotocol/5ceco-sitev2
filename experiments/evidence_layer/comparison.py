"""Human-authored comparison of two immutable JSON evidence artifacts.

The module counts reviewer-supplied classifications. It does not infer matches,
call a model, or inspect domain-specific evidence semantics.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from .canonical import canonical_json_bytes, canonical_json_text, canonical_sha256, sha256_hex


class ComparisonClassification(str, Enum):
    MATCHED_MATERIAL_FINDING = "MATCHED_MATERIAL_FINDING"
    MISSED_MATERIAL_FINDING = "MISSED_MATERIAL_FINDING"
    UNSUPPORTED_FALSE_POSITIVE = "UNSUPPORTED_FALSE_POSITIVE"
    JUDGEMENT_OVERREACH = "JUDGEMENT_OVERREACH"
    USEFUL_NON_MATERIAL_OBSERVATION = "USEFUL_NON_MATERIAL_OBSERVATION"


class ComparisonAuthorship(str, Enum):
    HUMAN_AUTHORED = "HUMAN_AUTHORED"


class ArtifactRole(str, Enum):
    GIGACARBON_OUTPUT = "gigacarbon_output"
    PRACTITIONER_AUDIT_READ = "practitioner_audit_read"


class ArtifactMutationError(RuntimeError):
    pass


class ComparisonValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class JsonArtifactReference:
    role: ArtifactRole
    sha256: str
    canonical_sha256: str
    source_path: str | None
    size_bytes: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", ArtifactRole(self.role))
        _require_sha256("sha256", self.sha256)
        _require_sha256("canonical_sha256", self.canonical_sha256)
        if self.source_path is not None:
            _require_text("source_path", self.source_path)
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ComparisonValidationError("size_bytes must be a non-negative integer")

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_sha256": self.canonical_sha256,
            "role": self.role.value,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "source_path": self.source_path,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JsonArtifactReference":
        return cls(
            role=ArtifactRole(payload["role"]),
            sha256=payload["sha256"],
            canonical_sha256=payload["canonical_sha256"],
            source_path=payload.get("source_path"),
            size_bytes=payload["size_bytes"],
        )


@dataclass(frozen=True, slots=True)
class ImmutableJsonArtifact:
    role: ArtifactRole
    sha256: str
    canonical_sha256: str
    source_path: str | None
    size_bytes: int
    _payload: Any

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", ArtifactRole(self.role))
        _require_sha256("sha256", self.sha256)
        _require_sha256("canonical_sha256", self.canonical_sha256)
        if self.source_path is not None:
            _require_text("source_path", self.source_path)
        if type(self.size_bytes) is not int or self.size_bytes < 0:
            raise ComparisonValidationError("size_bytes must be a non-negative integer")
        frozen_payload = _freeze_json(self._payload)
        if canonical_sha256(frozen_payload) != self.canonical_sha256:
            raise ComparisonValidationError("canonical_sha256 does not match the artifact payload")
        object.__setattr__(self, "_payload", frozen_payload)

    @classmethod
    def from_path(cls, path: str | Path, role: ArtifactRole) -> "ImmutableJsonArtifact":
        source_path = Path(path).resolve(strict=True)
        raw = source_path.read_bytes()
        payload = _parse_json(raw)
        return cls(
            role=ArtifactRole(role),
            sha256=sha256_hex(raw),
            canonical_sha256=canonical_sha256(payload),
            source_path=str(source_path),
            size_bytes=len(raw),
            _payload=_freeze_json(payload),
        )

    @classmethod
    def from_payload(cls, payload: Any, role: ArtifactRole) -> "ImmutableJsonArtifact":
        canonical = canonical_json_bytes(payload)
        return cls(
            role=ArtifactRole(role),
            sha256=sha256_hex(canonical),
            canonical_sha256=sha256_hex(canonical),
            source_path=None,
            size_bytes=len(canonical),
            _payload=_freeze_json(payload),
        )

    @property
    def payload(self) -> Any:
        return self._payload

    def reference(self) -> JsonArtifactReference:
        return JsonArtifactReference(
            role=self.role,
            sha256=self.sha256,
            canonical_sha256=self.canonical_sha256,
            source_path=self.source_path,
            size_bytes=self.size_bytes,
        )

    def assert_unchanged(self) -> None:
        if self.source_path is None:
            return
        path = Path(self.source_path)
        try:
            current = path.read_bytes()
        except OSError as exc:
            raise ArtifactMutationError(f"Source artifact is no longer readable: {path}") from exc
        current_hash = sha256_hex(current)
        if current_hash != self.sha256:
            raise ArtifactMutationError(
                f"Source artifact changed after it was loaded: {path}; "
                f"expected {self.sha256}, found {current_hash}"
            )


@dataclass(frozen=True, slots=True)
class ProvenanceReference:
    artifact_role: ArtifactRole
    artifact_sha256: str
    locator: str
    source_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_role", ArtifactRole(self.artifact_role))
        _require_sha256("artifact_sha256", self.artifact_sha256)
        _require_text("locator", self.locator)
        if self.source_id is not None:
            _require_text("source_id", self.source_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_role": self.artifact_role.value,
            "artifact_sha256": self.artifact_sha256,
            "locator": self.locator,
            "source_id": self.source_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProvenanceReference":
        return cls(
            artifact_role=ArtifactRole(payload["artifact_role"]),
            artifact_sha256=payload["artifact_sha256"],
            locator=payload["locator"],
            source_id=payload.get("source_id"),
        )


@dataclass(frozen=True, slots=True)
class ComparisonItem:
    case_id: str
    practitioner_finding_id: str
    gigacarbon_finding_ids: tuple[str, ...]
    classification: ComparisonClassification
    reviewer_rationale: str
    provenance_references: tuple[ProvenanceReference, ...]
    reviewer_identity: str
    timestamp: str
    authorship: ComparisonAuthorship = ComparisonAuthorship.HUMAN_AUTHORED

    def __post_init__(self) -> None:
        object.__setattr__(self, "classification", ComparisonClassification(self.classification))
        object.__setattr__(self, "authorship", ComparisonAuthorship(self.authorship))
        if isinstance(self.gigacarbon_finding_ids, (str, bytes, bytearray)):
            raise ComparisonValidationError(
                "gigacarbon_finding_ids must be a sequence of strings, not a string"
            )
        if isinstance(self.provenance_references, (str, bytes, bytearray)):
            raise ComparisonValidationError(
                "provenance_references must be a sequence, not a string"
            )
        object.__setattr__(self, "gigacarbon_finding_ids", tuple(self.gigacarbon_finding_ids))
        object.__setattr__(self, "provenance_references", tuple(self.provenance_references))
        for field_name in ("case_id", "practitioner_finding_id", "reviewer_rationale", "reviewer_identity"):
            _require_text(field_name, getattr(self, field_name))
        if any(not isinstance(item, str) or not item.strip() for item in self.gigacarbon_finding_ids):
            raise ComparisonValidationError("gigacarbon_finding_ids must contain only non-empty strings")
        if len(set(self.gigacarbon_finding_ids)) != len(self.gigacarbon_finding_ids):
            raise ComparisonValidationError("gigacarbon_finding_ids must not contain duplicates")
        if any(not isinstance(item, ProvenanceReference) for item in self.provenance_references):
            raise ComparisonValidationError("provenance_references must contain ProvenanceReference values")
        _require_timestamp("timestamp", self.timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorship": self.authorship.value,
            "case_id": self.case_id,
            "classification": self.classification.value,
            "gigacarbon_finding_ids": list(self.gigacarbon_finding_ids),
            "practitioner_finding_id": self.practitioner_finding_id,
            "provenance_references": [item.to_dict() for item in self.provenance_references],
            "reviewer_identity": self.reviewer_identity,
            "reviewer_rationale": self.reviewer_rationale,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ComparisonItem":
        return cls(
            case_id=payload["case_id"],
            practitioner_finding_id=payload["practitioner_finding_id"],
            gigacarbon_finding_ids=tuple(payload.get("gigacarbon_finding_ids", ())),
            classification=ComparisonClassification(payload["classification"]),
            reviewer_rationale=payload["reviewer_rationale"],
            provenance_references=tuple(
                ProvenanceReference.from_dict(item)
                for item in payload.get("provenance_references", ())
            ),
            reviewer_identity=payload["reviewer_identity"],
            timestamp=payload["timestamp"],
            authorship=ComparisonAuthorship(payload.get("authorship", "HUMAN_AUTHORED")),
        )


@dataclass(frozen=True, slots=True)
class Scorecard:
    counts: tuple[tuple[ComparisonClassification, int], ...]
    total_comparison_items: int
    material_findings_reviewed: int

    @classmethod
    def from_items(cls, items: tuple[ComparisonItem, ...]) -> "Scorecard":
        counts = tuple(
            (classification, sum(item.classification == classification for item in items))
            for classification in ComparisonClassification
        )
        count_map = dict(counts)
        return cls(
            counts=counts,
            total_comparison_items=len(items),
            material_findings_reviewed=(
                count_map[ComparisonClassification.MATCHED_MATERIAL_FINDING]
                + count_map[ComparisonClassification.MISSED_MATERIAL_FINDING]
            ),
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "counts",
            tuple((ComparisonClassification(key), value) for key, value in self.counts),
        )
        keys = tuple(key for key, _ in self.counts)
        if keys != tuple(ComparisonClassification):
            raise ComparisonValidationError("scorecard counts must contain every classification once in enum order")
        if any(type(value) is not int or value < 0 for _, value in self.counts):
            raise ComparisonValidationError("scorecard counts must be non-negative integers")
        if type(self.total_comparison_items) is not int or type(self.material_findings_reviewed) is not int:
            raise ComparisonValidationError("scorecard totals must be integers")
        if self.total_comparison_items != sum(value for _, value in self.counts):
            raise ComparisonValidationError("scorecard total does not match classification counts")
        material_total = dict(self.counts)[ComparisonClassification.MATCHED_MATERIAL_FINDING] + dict(self.counts)[
            ComparisonClassification.MISSED_MATERIAL_FINDING
        ]
        if self.material_findings_reviewed != material_total:
            raise ComparisonValidationError("material-findings total does not match classification counts")

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification_counts": {key.value: value for key, value in self.counts},
            "material_findings_reviewed": self.material_findings_reviewed,
            "total_comparison_items": self.total_comparison_items,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Scorecard":
        values = payload["classification_counts"]
        return cls(
            counts=tuple(
                (classification, values[classification.value])
                for classification in ComparisonClassification
            ),
            total_comparison_items=payload["total_comparison_items"],
            material_findings_reviewed=payload["material_findings_reviewed"],
        )


@dataclass(frozen=True, slots=True)
class CaseScorecard:
    case_id: str
    scorecard: Scorecard

    def __post_init__(self) -> None:
        _require_text("case_id", self.case_id)

    def to_dict(self) -> dict[str, Any]:
        return {"case_id": self.case_id, **self.scorecard.to_dict()}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CaseScorecard":
        return cls(case_id=payload["case_id"], scorecard=Scorecard.from_dict(payload))


@dataclass(frozen=True, slots=True)
class ComparisonRun:
    run_id: str
    generated_at: str
    gigacarbon_output: JsonArtifactReference
    practitioner_audit_read: JsonArtifactReference
    items: tuple[ComparisonItem, ...]
    per_case_scorecards: tuple[CaseScorecard, ...]
    aggregate_scorecard: Scorecard
    authorship: ComparisonAuthorship = ComparisonAuthorship.HUMAN_AUTHORED
    schema_version: str = "blind-evaluation-comparison/v1"

    def __post_init__(self) -> None:
        _require_text("run_id", self.run_id)
        _require_text("schema_version", self.schema_version)
        _require_timestamp("generated_at", self.generated_at)
        object.__setattr__(self, "authorship", ComparisonAuthorship(self.authorship))
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "per_case_scorecards", tuple(self.per_case_scorecards))
        if self.gigacarbon_output.role != ArtifactRole.GIGACARBON_OUTPUT:
            raise ComparisonValidationError("gigacarbon_output has the wrong artifact role")
        if self.practitioner_audit_read.role != ArtifactRole.PRACTITIONER_AUDIT_READ:
            raise ComparisonValidationError("practitioner_audit_read has the wrong artifact role")
        _validate_comparison_items(
            self.items,
            {
                self.gigacarbon_output.role: self.gigacarbon_output.sha256,
                self.practitioner_audit_read.role: self.practitioner_audit_read.sha256,
            },
        )
        expected_cases = tuple(
            CaseScorecard(case_id, Scorecard.from_items(tuple(item for item in self.items if item.case_id == case_id)))
            for case_id in sorted({item.case_id for item in self.items})
        )
        if self.per_case_scorecards != expected_cases:
            raise ComparisonValidationError("per-case scorecards do not match comparison items")
        if self.aggregate_scorecard != Scorecard.from_items(self.items):
            raise ComparisonValidationError("aggregate scorecard does not match comparison items")

    def to_dict(self) -> dict[str, Any]:
        return {
            "aggregate_scorecard": self.aggregate_scorecard.to_dict(),
            "authorship": self.authorship.value,
            "generated_at": self.generated_at,
            "inputs": {
                "gigacarbon_output": self.gigacarbon_output.to_dict(),
                "practitioner_audit_read": self.practitioner_audit_read.to_dict(),
            },
            "items": [item.to_dict() for item in self.items],
            "per_case_scorecards": [item.to_dict() for item in self.per_case_scorecards],
            "run_id": self.run_id,
            "schema_version": self.schema_version,
        }

    @property
    def sha256(self) -> str:
        """Hash of the canonical `comparison` payload in the output envelope."""
        return canonical_sha256(self.to_dict())

    def to_output_dict(self) -> dict[str, Any]:
        return {"comparison": self.to_dict(), "comparison_sha256": self.sha256}

    def to_canonical_json(self) -> str:
        return canonical_json_text(self.to_output_dict())

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ComparisonRun":
        inputs = payload["inputs"]
        return cls(
            run_id=payload["run_id"],
            generated_at=payload["generated_at"],
            gigacarbon_output=JsonArtifactReference.from_dict(inputs["gigacarbon_output"]),
            practitioner_audit_read=JsonArtifactReference.from_dict(inputs["practitioner_audit_read"]),
            items=tuple(ComparisonItem.from_dict(item) for item in payload.get("items", ())),
            per_case_scorecards=tuple(
                CaseScorecard.from_dict(item) for item in payload.get("per_case_scorecards", ())
            ),
            aggregate_scorecard=Scorecard.from_dict(payload["aggregate_scorecard"]),
            authorship=ComparisonAuthorship(payload.get("authorship", "HUMAN_AUTHORED")),
            schema_version=payload["schema_version"],
        )

    @classmethod
    def from_canonical_json(cls, serialized: str | bytes) -> "ComparisonRun":
        output = json.loads(serialized)
        if not isinstance(output, dict) or not isinstance(output.get("comparison"), dict):
            raise ComparisonValidationError("Comparison output must be a JSON object envelope")
        run = cls.from_dict(output["comparison"])
        if output.get("comparison_sha256") != run.sha256:
            raise ComparisonValidationError("Comparison output SHA-256 does not match its canonical payload")
        return run


@dataclass(frozen=True, slots=True)
class WrittenComparisonOutput:
    path: str
    file_sha256: str
    comparison_sha256: str
    generated_at: str


def build_human_comparison(
    *,
    run_id: str,
    generated_at: str,
    gigacarbon_output: ImmutableJsonArtifact,
    practitioner_audit_read: ImmutableJsonArtifact,
    items: tuple[ComparisonItem, ...],
) -> ComparisonRun:
    """Count human-authored items without deciding whether any finding matches."""
    artifacts = (gigacarbon_output, practitioner_audit_read)
    _assert_expected_roles(gigacarbon_output, practitioner_audit_read)
    for artifact in artifacts:
        artifact.assert_unchanged()
    try:
        supplied_items = tuple(items)
        if any(not isinstance(item, ComparisonItem) for item in supplied_items):
            raise ComparisonValidationError("items must contain ComparisonItem values")
        normalized_items = tuple(sorted(supplied_items, key=lambda item: canonical_json_bytes(item.to_dict())))
        case_scorecards = tuple(
            CaseScorecard(
                case_id,
                Scorecard.from_items(tuple(item for item in normalized_items if item.case_id == case_id)),
            )
            for case_id in sorted({item.case_id for item in normalized_items})
        )
        return ComparisonRun(
            run_id=run_id,
            generated_at=generated_at,
            gigacarbon_output=gigacarbon_output.reference(),
            practitioner_audit_read=practitioner_audit_read.reference(),
            items=normalized_items,
            per_case_scorecards=case_scorecards,
            aggregate_scorecard=Scorecard.from_items(normalized_items),
        )
    finally:
        for artifact in artifacts:
            artifact.assert_unchanged()


def write_new_comparison_output(
    path: str | Path,
    comparison: ComparisonRun,
    *,
    source_artifacts: tuple[ImmutableJsonArtifact, ...],
) -> WrittenComparisonOutput:
    """Write a new output exclusively; refuse source paths and existing targets."""
    _validate_output_source_artifacts(comparison, source_artifacts)
    for artifact in source_artifacts:
        artifact.assert_unchanged()
    output_path = Path(path).resolve(strict=False)
    source_paths = {
        Path(artifact.source_path).resolve(strict=True)
        for artifact in source_artifacts
        if artifact.source_path is not None
    }
    if output_path in source_paths:
        raise ComparisonValidationError("Comparison output path must not be a source artifact")
    serialized = comparison.to_canonical_json().encode("utf-8") + b"\n"
    try:
        with output_path.open("xb") as output_file:
            output_file.write(serialized)
    finally:
        for artifact in source_artifacts:
            artifact.assert_unchanged()
    return WrittenComparisonOutput(
        path=str(output_path),
        file_sha256=sha256_hex(serialized),
        comparison_sha256=comparison.sha256,
        generated_at=comparison.generated_at,
    )


def _assert_expected_roles(
    gigacarbon_output: ImmutableJsonArtifact,
    practitioner_audit_read: ImmutableJsonArtifact,
) -> None:
    if gigacarbon_output.role != ArtifactRole.GIGACARBON_OUTPUT:
        raise ComparisonValidationError("First input must have the gigacarbon_output role")
    if practitioner_audit_read.role != ArtifactRole.PRACTITIONER_AUDIT_READ:
        raise ComparisonValidationError("Second input must have the practitioner_audit_read role")


def _validate_comparison_items(
    items: tuple[ComparisonItem, ...],
    expected_hashes: dict[ArtifactRole, str],
) -> None:
    if any(not isinstance(item, ComparisonItem) for item in items):
        raise ComparisonValidationError("items must contain ComparisonItem values")
    finding_keys = tuple((item.case_id, item.practitioner_finding_id) for item in items)
    if len(set(finding_keys)) != len(finding_keys):
        raise ComparisonValidationError(
            "Each practitioner finding ID must appear at most once per case"
        )
    for item in items:
        if item.authorship != ComparisonAuthorship.HUMAN_AUTHORED:
            raise ComparisonValidationError("Every comparison item must be human-authored")
        for reference in item.provenance_references:
            if reference.artifact_sha256 != expected_hashes[reference.artifact_role]:
                raise ComparisonValidationError(
                    f"Provenance hash does not match the {reference.artifact_role.value} input"
                )


def _validate_output_source_artifacts(
    comparison: ComparisonRun,
    artifacts: tuple[ImmutableJsonArtifact, ...],
) -> None:
    expected = {
        ArtifactRole.GIGACARBON_OUTPUT: comparison.gigacarbon_output,
        ArtifactRole.PRACTITIONER_AUDIT_READ: comparison.practitioner_audit_read,
    }
    if len(artifacts) != len(expected) or {artifact.role for artifact in artifacts} != set(expected):
        raise ComparisonValidationError("source_artifacts must contain both comparison inputs exactly once")
    for artifact in artifacts:
        if artifact.reference() != expected[artifact.role]:
            raise ComparisonValidationError(
                f"Source artifact does not match the comparison's {artifact.role.value} input"
            )


def _parse_json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ComparisonValidationError("Artifact must be valid UTF-8 JSON") from exc


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, bool, int, float)):
        canonical_json_bytes(value)
        return value
    raise ComparisonValidationError(f"Unsupported JSON value: {type(value).__name__}")


def _require_text(field_name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ComparisonValidationError(f"{field_name} must be a non-empty string")


def _require_timestamp(field_name: str, value: Any) -> None:
    _require_text(field_name, value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ComparisonValidationError(f"{field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ComparisonValidationError(f"{field_name} must include a timezone")


def _require_sha256(field_name: str, value: Any) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ComparisonValidationError(f"{field_name} must be a lowercase SHA-256 hex digest")
    try:
        decoded = bytes.fromhex(value)
    except ValueError as exc:
        raise ComparisonValidationError(f"{field_name} must be a lowercase SHA-256 hex digest") from exc
    if len(decoded) != 32 or value != value.lower():
        raise ComparisonValidationError(f"{field_name} must be a lowercase SHA-256 hex digest")
