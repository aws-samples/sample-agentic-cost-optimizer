#!/usr/bin/env python3
"""Generate infra/constants/event-statuses.ts from src/shared/event_statuses.py.

Usage: generate-event-statuses.py <output-path>

src/shared/event_statuses.py is the single source of truth for event status
strings. This script mirrors it into a TypeScript module so the Step
Functions workflow (infra/lib/workflow.ts) can't drift from the Python
values that actually get written to DynamoDB.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.shared.event_statuses import EventStatus  # noqa: E402

HEADER = """// GENERATED FILE — do not edit by hand.
// Source of truth: src/shared/event_statuses.py
// Regenerated automatically by `npm run generate-event-statuses` (part of `npm run build`).
"""


def render(statuses: dict[str, str]) -> str:
    entries = "\n".join(f"  {name}: '{value}'," for name, value in statuses.items())
    return (
        f"{HEADER}\n"
        f"export const EventStatus = {{\n{entries}\n}} as const;\n\n"
        f"export type EventStatusType = (typeof EventStatus)[keyof typeof EventStatus];\n"
    )


def main() -> None:
    output_path = Path(sys.argv[1])
    statuses = {name: value for name, value in vars(EventStatus).items() if not name.startswith("_")}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render(statuses))


if __name__ == "__main__":
    main()
