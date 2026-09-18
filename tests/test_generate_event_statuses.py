"""Unit tests for scripts/generate-event-statuses.py."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate-event-statuses.py"

_spec = importlib.util.spec_from_file_location("generate_event_statuses", SCRIPT_PATH)
generate_event_statuses = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_event_statuses)


def test_render_mirrors_provided_statuses():
    output = generate_event_statuses.render({"FOO": "FOO", "BAR": "BAR_VALUE"})

    assert "FOO: 'FOO'," in output
    assert "BAR: 'BAR_VALUE'," in output
    assert "export const EventStatus" in output
    assert "as const" in output
    assert "export type EventStatusType" in output


def test_render_preserves_insertion_order():
    output = generate_event_statuses.render({"A": "1", "B": "2", "C": "3"})

    assert output.index("A: '1'") < output.index("B: '2'") < output.index("C: '3'")


def test_main_mirrors_every_real_event_status(tmp_path, monkeypatch):
    from src.shared.event_statuses import EventStatus

    output_path = tmp_path / "event-statuses.ts"
    monkeypatch.setattr("sys.argv", ["generate-event-statuses.py", str(output_path)])

    generate_event_statuses.main()

    content = output_path.read_text()
    expected = {name: value for name, value in vars(EventStatus).items() if not name.startswith("_")}

    assert expected, "EventStatus should not be empty"
    for name, value in expected.items():
        assert f"{name}: '{value}'," in content
    assert "GENERATED FILE" in content
