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
