"""Usage and Metrics Collection Phase Evaluation."""

from pathlib import Path

import pytest
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall, ToolCallParams
from strands import Agent
from strands.models import BedrockModel

from evals.conftest import (
    AWS_REGION,
    MODEL_ID,
    create_calculator_tool,
    create_journal_tool,
    create_time_tool,
    create_use_aws_tool,
)
from evals.helpers import print_eval_results


def load_metrics_prompt() -> str:
    """Extract Usage and Metrics Collection phase from analysis_prompt.md."""
    prompt_path = Path(__file__).parent.parent.parent / "src" / "agents" / "analysis_prompt.md"
    full_prompt = prompt_path.read_text()

    lines = full_prompt.split("\n")
    start_idx = next(i for i, line in enumerate(lines) if "2) Usage and Metrics Collection" in line)
    end_idx = next(i for i, line in enumerate(lines) if "3) Analysis and Decision Rules" in line and i > start_idx)

    return f"""# Cost Optimization Agent - Usage and Metrics Collection Phase

You are an AWS Technical Account Manager. Perform ONLY the Usage and Metrics Collection phase, then STOP.

## Context

You have already completed Discovery and found this Lambda function:
- payment-processor (1024 MB, python3.12, x86_64)

## Journaling

Track your progress with the journal tool:
- Start: journal(action="start_task", phase_name="Usage and Metrics Collection")
- Complete: journal(action="complete_task", phase_name="Usage and Metrics Collection", status="COMPLETED")

## Time Tools

Use these tools for time calculations:
- current_time_unix_utc() - returns current Unix timestamp
- calculator(expression="...") - for arithmetic (e.g., time range calculations)

## Workflow

{chr(10).join(lines[start_idx:end_idx])}

## IMPORTANT

After collecting CloudWatch metrics and Logs Insights data for the function, STOP immediately.
Do NOT proceed to Analysis phase. Report metrics findings and end.
"""


@pytest.fixture
def mock_tools(capture):
    return [
        create_journal_tool(capture),
        create_time_tool(capture),
        create_calculator_tool(capture),
        create_use_aws_tool(capture),
    ]


@pytest.fixture
def prompt():
    return load_metrics_prompt()


@pytest.fixture
def agent(mock_tools, prompt):
    model = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
    return Agent(model=model, system_prompt=prompt, tools=mock_tools)


class TestMetricsPhase:
    """Usage and Metrics Collection phase evaluation."""

    def test_metrics_phase(self, agent, capture, deepeval_model, prompt):
        """Validate Metrics phase tool sequence and parameters."""
        result = agent("Collect usage metrics for the payment-processor Lambda function")

        expected_tools = [
            ToolCall(
                name="journal",
                input_parameters={"action": "start_task", "phase_name": "Usage and Metrics Collection", "status": None},
            ),
            ToolCall(name="current_time_unix_utc", input_parameters={}),
            ToolCall(
                name="journal",
                input_parameters={
                    "action": "complete_task",
                    "phase_name": "Usage and Metrics Collection",
                    "status": "COMPLETED",
                },
            ),
        ]

        test_case = LLMTestCase(
            input="Collect usage metrics for the payment-processor Lambda function",
            actual_output=str(result),
            tools_called=capture.calls,
            expected_tools=expected_tools,
        )

        metric = ToolCorrectnessMetric(
            model=deepeval_model,
            evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
            should_consider_ordering=False,
            threshold=0.7,
        )
        metric.measure(test_case)

        metrics_summary = agent.event_loop_metrics.get_summary()
        print_eval_results(
            phase_name="Metrics",
            prompt_chars=len(prompt),
            metric_score=metric.score,
            metric_reason=metric.reason,
            capture=capture,
            token_usage=metrics_summary.get("accumulated_usage", {}),
            metrics_summary=metrics_summary,
        )

        assert metric.score >= 0.7, f"Tool correctness failed: {metric.reason}"
