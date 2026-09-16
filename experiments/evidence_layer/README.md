# Evidence-layer prototype

This isolated, synthetic prototype turns one Fuel Portal record and zero or one
Field Report record into an explicit evidence state. It does not modify the
production website, `/pilot`, or any source observation.

## Run

From the repository root:

```sh
python3 -m unittest discover -s experiments/evidence_layer/tests -v
python3 -m experiments.evidence_layer.demo
```

The demo prints compact JSON followed by a nine-part human-readable explanation
for each synthetic case.

## Boundary

The engine deterministically identifies candidates using either a shared
transaction reference or at least three exact operational fields. Candidate
status is not treated as proof that records are equivalent. It then compares named fields, distinguishes event time
from posting time, records missingness, validates the completeness of an
explicit resolution, and blocks downstream output while conflicts or required
evidence remain open. It does not infer a correct vehicle, estimate missing
odometers, decide whether an absent field entry means an event did not happen,
or accept a correction without a named resolver and cited evidence.

This is not production-ready and does not ingest real company records.

## Additive generic primitives

`evidence_item.py` defines a domain-neutral `EvidenceItem` with the states
`SUPPORTED`, `CONFLICTING`, `MISSING`, `NOT_ESTABLISHED`, and
`HUMAN_JUDGEMENT_REQUIRED`. It is separate from the existing `EvidenceState`,
so existing source, conflict, gap, resolution, and serialization behavior is
unchanged.

`comparison.py` compares immutable JSON artifact identities using only
human-authored `ComparisonItem` decisions. It does not infer matches or call a
model. It produces per-case and aggregate classification counts, canonical
JSON, and a SHA-256 over the canonical comparison payload. Its output writer
uses exclusive creation and refuses either source artifact as an output path.
