"""
Discovery Phase Evaluation using DeepEval

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

from .conftest import AWS_REGION, MOCK_LAMBDA_FUNCTIONS, MODEL_ID


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


# =============================================================================
# FIXTURES
# =============================================================================


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
def agent(mock_tools):
    """Create Discovery agent with real prompt."""
    model = BedrockModel(model_id=MODEL_ID, region_name=AWS_REGION)
    return Agent(model=model, system_prompt=load_discovery_prompt(), tools=mock_tools)


# =============================================================================
# TESTS
# =============================================================================


class TestDiscoveryPhase:
    """
    Discovery phase evaluation."""

    def test_discovery_phase(self, agent, capture, deepeval_model):
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
                    "status": None,  # Not used for start_task
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

        # Print evaluation results
        print(f"\n{'=' * 60}")
        print("DISCOVERY PHASE EVALUATION")
        print(f"{'=' * 60}")

        # DeepEval metric results
        print(f"\nScore: {metric.score}")
        print(f"Reason: {metric.reason}")

        # Tool calls captured
        print(f"\nTool Calls: {capture.names}")
        for i, call in enumerate(capture.calls):
            print(f"  {i + 1}. {call.name}({call.input_parameters})")

        print(f"\n{'=' * 60}")

        # Assertion
        assert metric.score >= 0.9, f"Tool correctness failed: {metric.reason}"
