"""Analysis Agent Evaluation.

Tests the analysis agent workflow with mocked AWS tool responses.
"""

from pathlib import Path

import pytest
from deepeval.metrics import TaskCompletionMetric, ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall, ToolCallParams
from strands import Agent
from strands.models import BedrockModel

from evals.conftest import (
    AGENT_MODEL_ID,
    AWS_REGION,
    create_calculator_tool,
    create_journal_tool,
    create_storage_tool,
    create_time_tool,
    create_use_aws_tool,
)
from evals.helpers import print_eval_results


def load_full_analysis_prompt() -> str:
    """Load the complete analysis prompt."""
    prompt_path = Path(__file__).parent.parent / "src" / "agents" / "analysis_prompt.md"
    return prompt_path.read_text()


@pytest.fixture
def mock_tools(capture):
    return [
        create_journal_tool(capture),
        create_time_tool(capture),
        create_calculator_tool(capture),
        create_use_aws_tool(capture),
        create_storage_tool(capture),
    ]


@pytest.fixture
def prompt():
    return load_full_analysis_prompt()


@pytest.fixture
def agent(mock_tools, prompt):
    model = BedrockModel(model_id=AGENT_MODEL_ID, region_name=AWS_REGION)
    return Agent(model=model, system_prompt=prompt, tools=mock_tools)


class TestAnalysisAgent:
    """Analysis agent evaluation with mocked tools."""

    def test_full_workflow(self, agent, capture, judge_model, prompt):
        """Validate complete workflow: Discovery → Metrics → Analysis → Recommendations → Cost Estimation → Storage."""
        result = agent("Analyze Lambda functions for cost optimization opportunities")

        # Expected: journal bookends for each phase + storage at end
        # We check key tools are called, not exact sequence (too variable)
        expected_tools = [
            # Discovery phase
            ToolCall(
                name="journal", input_parameters={"action": "start_task", "phase_name": "Discovery", "status": None}
            ),
            ToolCall(name="use_aws", input_parameters={"service": "lambda", "action": "list_functions"}),
            ToolCall(
                name="journal",
                input_parameters={"action": "complete_task", "phase_name": "Discovery", "status": "COMPLETED"},
            ),
            # Metrics phase
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
            # Analysis phase
            ToolCall(
                name="journal",
                input_parameters={"action": "start_task", "phase_name": "Analysis and Decision Rules", "status": None},
            ),
            ToolCall(
                name="journal",
                input_parameters={
                    "action": "complete_task",
                    "phase_name": "Analysis and Decision Rules",
                    "status": "COMPLETED",
                },
            ),
            # Recommendation phase
            ToolCall(
                name="journal",
                input_parameters={"action": "start_task", "phase_name": "Recommendation Format", "status": None},
            ),
            ToolCall(
                name="journal",
                input_parameters={
                    "action": "complete_task",
                    "phase_name": "Recommendation Format",
                    "status": "COMPLETED",
                },
            ),
            # Cost Estimation phase
            ToolCall(
                name="journal",
                input_parameters={"action": "start_task", "phase_name": "Cost Estimation Method", "status": None},
            ),
            ToolCall(
                name="journal",
                input_parameters={
                    "action": "complete_task",
                    "phase_name": "Cost Estimation Method",
                    "status": "COMPLETED",
                },
            ),
            # Final storage
            ToolCall(name="storage", input_parameters={"action": "write", "filename": "analysis.txt"}),
        ]

        test_case = LLMTestCase(
            input="Analyze Lambda functions for cost optimization opportunities",
            actual_output=str(result),
            tools_called=capture.calls,
            expected_tools=expected_tools,
        )

        available_tools = [
            ToolCall(name="journal", description="Track workflow phases with start_task and complete_task actions"),
            ToolCall(name="use_aws", description="Call AWS APIs for Lambda, CloudWatch, and Pricing services"),
            ToolCall(name="current_time_unix_utc", description="Get current Unix timestamp in UTC"),
            ToolCall(name="calculator", description="Evaluate arithmetic expressions for cost calculations"),
            ToolCall(name="storage", description="Read and write analysis results to S3 storage"),
        ]

        # Metric 1: Tool Correctness (judged by Llama)
        tool_metric = ToolCorrectnessMetric(
            model=judge_model,
            evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
            available_tools=available_tools,
            should_consider_ordering=False,
            threshold=0.7,
        )
        tool_metric.measure(test_case)

        # Metric 2: Task Completion (judged by Llama)
        task_metric = TaskCompletionMetric(
            task="Analyze Lambda functions, collect CloudWatch metrics, identify cost optimization opportunities, and save analysis results with specific recommendations and savings estimates",
            model=judge_model,
            threshold=0.7,
        )
        task_metric.measure(test_case)

        # Print results
        print_eval_results(
            phase_name="Analysis Agent",
            tool_score=tool_metric.score,
            tool_reason=tool_metric.reason,
            task_score=task_metric.score,
            task_reason=task_metric.reason,
            capture=capture,
            token_usage=agent.event_loop_metrics.get_summary().get("accumulated_usage", {}),
        )

        assert tool_metric.score >= 0.7, f"Tool correctness failed: {tool_metric.reason}"
        assert task_metric.score >= 0.7, f"Task completion failed: {task_metric.reason}"
