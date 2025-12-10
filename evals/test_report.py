"""Report Agent Evaluation.

Tests the report agent workflow with mocked storage (S3) responses.
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
    ToolCapture,
    create_journal_tool,
    create_storage_tool,
)
from evals.helpers import print_eval_results
from evals.mock_data import MOCK_ANALYSIS_RESULT


def load_report_prompt() -> str:
    """Load the report agent prompt."""
    prompt_path = Path(__file__).parent.parent / "src" / "agents" / "report_prompt.md"
    return prompt_path.read_text()


@pytest.fixture
def report_capture():
    """Fresh tool capture for report agent test."""
    return ToolCapture()


@pytest.fixture
def report_tools(report_capture):
    return [
        create_journal_tool(report_capture),
        create_storage_tool(report_capture, mock_read_content=MOCK_ANALYSIS_RESULT),
    ]


@pytest.fixture
def report_prompt():
    return load_report_prompt()


@pytest.fixture
def report_agent(report_tools, report_prompt):
    model = BedrockModel(model_id=AGENT_MODEL_ID, region_name=AWS_REGION)
    return Agent(model=model, system_prompt=report_prompt, tools=report_tools)


class TestReportAgent:
    """Report agent evaluation with mocked storage."""

    def test_full_workflow(self, report_agent, report_capture, judge_model, report_prompt):
        """Validate report generation: Load Analysis → Generate Report → Write to S3."""
        result = report_agent("Generate the cost optimization report")

        expected_tools = [
            # Load analysis data
            ToolCall(name="storage", input_parameters={"action": "read", "filename": "analysis.txt"}),
            # Output Contract phase
            ToolCall(
                name="journal",
                input_parameters={"action": "start_task", "phase_name": "Output Contract", "status": None},
            ),
            ToolCall(
                name="journal",
                input_parameters={"action": "complete_task", "phase_name": "Output Contract", "status": "COMPLETED"},
            ),
            # S3 Write phase
            ToolCall(
                name="journal",
                input_parameters={"action": "start_task", "phase_name": "S3 Write Requirements", "status": None},
            ),
            ToolCall(name="storage", input_parameters={"action": "write", "filename": "cost_report.txt"}),
            ToolCall(name="storage", input_parameters={"action": "write", "filename": "evidence.txt"}),
            ToolCall(
                name="journal",
                input_parameters={
                    "action": "complete_task",
                    "phase_name": "S3 Write Requirements",
                    "status": "COMPLETED",
                },
            ),
        ]

        test_case = LLMTestCase(
            input="Generate the cost optimization report",
            actual_output=str(result),
            tools_called=report_capture.calls,
            expected_tools=expected_tools,
        )

        available_tools = [
            ToolCall(name="journal", description="Track workflow phases with start_task and complete_task actions"),
            ToolCall(name="storage", description="Read and write files to S3 storage"),
        ]

        # Metric 1: Tool Correctness
        tool_metric = ToolCorrectnessMetric(
            model=judge_model,
            evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
            available_tools=available_tools,
            should_consider_ordering=False,
            threshold=0.7,
        )
        tool_metric.measure(test_case)

        # Metric 2: Task Completion
        task_metric = TaskCompletionMetric(
            task="Load analysis results from storage, generate a cost optimization report with executive summary and recommendations, and save both the report and evidence files to S3",
            model=judge_model,
            threshold=0.7,
        )
        task_metric.measure(test_case)

        # Print results
        metrics_summary = report_agent.event_loop_metrics.get_summary()
        print_eval_results(
            phase_name="Report Agent",
            prompt_chars=len(report_prompt),
            tool_score=tool_metric.score,
            tool_reason=tool_metric.reason,
            task_score=task_metric.score,
            task_reason=task_metric.reason,
            capture=report_capture,
            token_usage=metrics_summary.get("accumulated_usage", {}),
            metrics_summary=metrics_summary,
        )

        assert tool_metric.score >= 0.7, f"Tool correctness failed: {tool_metric.reason}"
        assert task_metric.score >= 0.7, f"Task completion failed: {task_metric.reason}"
