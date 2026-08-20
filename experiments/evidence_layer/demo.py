from __future__ import annotations

import json

from .fixtures import all_cases
from .reconcile import reconcile
from .render import human_summary


def main() -> None:
    for case in all_cases():
        state = reconcile(
            case.case_id,
            case.portal,
            case.field,
            context_sources=case.context_sources,
            resolution=case.resolution,
            require_monthly_kmpl=case.require_monthly_kmpl,
        )
        print(f"=== {case.description} ===")
        print(json.dumps(state.to_dict(), separators=(",", ":"), sort_keys=True))
        print(human_summary(state))
        print()


if __name__ == "__main__":
    main()
