"""Discovery Phase Evaluation."""

from pathlib import Path

import pytest
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall, ToolCallParams
from strands import Agent
from strands.models import BedrockModel

from evals.conftest import (
    AWS_REGION,
    MODEL_ID,
    create_journal_tool,
    create_use_aws_tool,
)
from evals.helpers import print_eval_results


def load_discovery_prompt() -> str:
    """Extract Discovery phase from analysis_prompt.md."""
    prompt_path = Path(__file__).parent.parent.parent / "src" / "agents" / "analysis_prompt.md"
    full_prompt = prompt_path.read_text()

    lines = full_prompt.split("\n")
    start_idx = next(i for i, line in enumerate(lines) if "1) Discovery (Inventory)" in line)
    end_idx = next(i for i, line in enumerate(lines) if "2) Usage and Metrics" in line and i > start_idx)

    return f"""# Cost Optimization Agent - Discovery Phase

You are an AWS Technical Account Manager. Perform ONLY the Discovery phase, then STOP.

## Journaling

Track your progress with the journal tool:
- Start: journal(action="start_task", phase_name="Discovery")
- Complete: journal(action="complete_task", phase_name="Discovery", status="COMPLETED")

## Workflow

{chr(10).join(lines[start_idx:end_idx])}

## IMPORTANT

After calling list_functions, STOP immediately.
Do NOT call get_function, get_function_configuration, or any other APIs.
Do NOT proceed to other phases. Report findings and end.
"""


@pytest.fixture
def mock_tools(capture):
    return [create_journal_tool(capture), create_use_aws_tool(capture)]


@pytest.fixture
def prompt():
    return load_discovery_prompt()


@pytest.fixture
def agent(mock_tools, prompt):
    model = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
    return Agent(model=model, system_prompt=prompt, tools=mock_tools)


class TestDiscoveryPhase:
    """Discovery phase evaluation."""

    def test_discovery_phase(self, agent, capture, deepeval_model, prompt):
        """Validate Discovery phase tool sequence and parameters."""
        result = agent("Perform Lambda function discovery")

        expected_tools = [
            ToolCall(
                name="journal", input_parameters={"action": "start_task", "phase_name": "Discovery", "status": None}
            ),
            ToolCall(name="use_aws", input_parameters={"service": "lambda", "action": "list_functions"}),
            ToolCall(
                name="journal",
                input_parameters={"action": "complete_task", "phase_name": "Discovery", "status": "COMPLETED"},
            ),
        ]

        test_case = LLMTestCase(
            input="Perform Lambda function discovery",
            actual_output=str(result),
            tools_called=capture.calls,
            expected_tools=expected_tools,
        )

        metric = ToolCorrectnessMetric(
            model=deepeval_model,
            evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
            should_consider_ordering=True,
            threshold=0.9,
        )
        metric.measure(test_case)

        metrics_summary = agent.event_loop_metrics.get_summary()
        print_eval_results(
            phase_name="Discovery",
            prompt_chars=len(prompt),
            metric_score=metric.score,
            metric_reason=metric.reason,
            capture=capture,
            token_usage=metrics_summary.get("accumulated_usage", {}),
            metrics_summary=metrics_summary,
        )

        assert metric.score >= 0.9, f"Tool correctness failed: {metric.reason}"
