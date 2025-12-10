"""
Discovery Phase Evaluation

Tests the Discovery phase using:
- Real Strands Agent with Bedrock LLM
- Real prompt extracted from analysis_prompt.md
- DeepEval's ToolCorrectnessMetric with Bedrock model
"""

from pathlib import Path

import pytest
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCase, ToolCall, ToolCallParams
from strands import Agent, tool
from strands.models import BedrockModel

from evals.conftest import AWS_REGION, MOCK_LAMBDA_FUNCTIONS, MODEL_ID, ToolCapture


def load_discovery_prompt() -> str:
    """Extract Discovery phase from the real analysis_prompt.md."""
    prompt_path = Path(__file__).parent.parent.parent / "src" / "agents" / "analysis_prompt.md"
    full_prompt = prompt_path.read_text()

    # Find Discovery section boundaries
    lines = full_prompt.split("\n")
    start_idx = next(i for i, line in enumerate(lines) if "1) Discovery (Inventory)" in line)
    end_idx = next(i for i, line in enumerate(lines) if "2) Usage and Metrics" in line and i > start_idx)

    discovery_section = "\n".join(lines[start_idx:end_idx])

    return f"""# Cost Optimization Agent - Discovery Phase

You are an AWS Technical Account Manager. Perform ONLY the Discovery phase, then STOP.

## Journaling

Track your progress with the journal tool:
- Start: journal(action="start_task", phase_name="Discovery")
- Complete: journal(action="complete_task", phase_name="Discovery", status="COMPLETED")

## Workflow

{discovery_section}

## IMPORTANT

After calling list_functions, STOP immediately.
Do NOT call get_function, get_function_configuration, or any other APIs.
Do NOT proceed to other phases. Report findings and end.
"""


@pytest.fixture
def capture():
    """Fresh tool capture for each test."""
    return ToolCapture()


@pytest.fixture
def mock_tools(capture):
    """Mock tools that capture invocations for Discovery phase."""

    @tool
    def journal(action: str, phase_name: str = None, status: str = None, error_message: str = None) -> dict:
        """Track workflow phases."""
        capture.record("journal", action=action, phase_name=phase_name, status=status)
        return {"success": True, "session_id": "eval-session"}

    @tool
    def use_aws(service: str, action: str, **kwargs) -> dict:
        """Call AWS APIs. Use service='lambda', action='list_functions' to list Lambda functions."""
        capture.record("use_aws", service=service, action=action)
        if service == "lambda" and action == "list_functions":
            return MOCK_LAMBDA_FUNCTIONS
        return {"error": "Not implemented in eval mock"}

    return [journal, use_aws]


@pytest.fixture
def discovery_prompt():
    """Load and return the discovery prompt for inspection."""
    return load_discovery_prompt()


@pytest.fixture
def agent(mock_tools, discovery_prompt):
    """Create Discovery agent with real prompt."""
    model = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
    return Agent(model=model, system_prompt=discovery_prompt, tools=mock_tools)


class TestDiscoveryPhase:
    """Discovery phase evaluation."""

    def test_discovery_phase(self, agent, capture, deepeval_model, discovery_prompt):
        """
        Evaluate the complete Discovery phase.

        Validates:
        - Tool sequence: journal(start) → use_aws(list_functions) → journal(complete)
        - Tool parameters: correct action, phase_name, service, status values
        """
        # Agent invocation
        result = agent("Perform Lambda function discovery")
        output = str(result)

        # Expected tool calls with parameters
        expected_tools = [
            ToolCall(
                name="journal",
                input_parameters={
                    "action": "start_task",
                    "phase_name": "Discovery",
                    "status": None,
                },
            ),
            ToolCall(
                name="use_aws",
                input_parameters={"service": "lambda", "action": "list_functions"},
            ),
            ToolCall(
                name="journal",
                input_parameters={
                    "action": "complete_task",
                    "phase_name": "Discovery",
                    "status": "COMPLETED",
                },
            ),
        ]

        test_case = LLMTestCase(
            input="Perform Lambda function discovery",
            actual_output=output,
            tools_called=capture.calls,
            expected_tools=expected_tools,
        )

        # Evaluate with DeepEval
        metric = ToolCorrectnessMetric(
            model=deepeval_model,
            evaluation_params=[ToolCallParams.INPUT_PARAMETERS],
            should_consider_ordering=True,
            threshold=0.9,
        )
        metric.measure(test_case)

        # Get metrics from agent
        metrics_summary = agent.event_loop_metrics.get_summary()
        token_usage = metrics_summary.get("accumulated_usage", {})

        # Print evaluation results
        print(f"\n{'-' * 40}")
        print("DISCOVERY PHASE EVALUATION")
        print(f"{'-' * 40}")
        print(f"\nSystem Prompt: {len(discovery_prompt)} chars")
        print(f"Score: {metric.score}")
        print(f"Reason: {metric.reason}")
        print(f"\nTool Calls: {capture.names}")
        for i, call in enumerate(capture.calls):
            print(f"  {i + 1}. {call.name}({call.input_parameters})")

        # Token usage stats
        print(f"\n{'-' * 40}")
        print("TOKEN USAGE")
        print(f"{'-' * 40}")
        print(f"  Input Tokens:  {token_usage.get('inputTokens', 'N/A')}")
        print(f"  Output Tokens: {token_usage.get('outputTokens', 'N/A')}")
        print(f"  Total Tokens:  {token_usage.get('totalTokens', 'N/A')}")
        if token_usage.get("cacheReadInputTokens"):
            print(f"  Cache Read:    {token_usage.get('cacheReadInputTokens')}")
        if token_usage.get("cacheWriteInputTokens"):
            print(f"  Cache Write:   {token_usage.get('cacheWriteInputTokens')}")

        # Execution stats
        print(f"\n{'-' * 40}")
        print("TEST EXECUTION STATS")
        print(f"{'-' * 40}")
        cycle_count = metrics_summary.get("cycle_count") or metrics_summary.get("cycles", "N/A")
        total_duration = metrics_summary.get("total_duration")
        avg_cycle = metrics_summary.get("average_cycle_time")
        print(f"  Cycles:        {cycle_count}")
        print(f"  Duration:      {total_duration:.2f}s" if total_duration else "  Duration:      N/A")
        print(f"  Avg Cycle:     {avg_cycle:.2f}s" if avg_cycle else "  Avg Cycle:     N/A")
        print(f"\n{'-' * 40}")

        # Assertion
        assert metric.score >= 0.9, f"Tool correctness failed: {metric.reason}"
