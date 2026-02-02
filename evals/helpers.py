"""
Helper functions for evaluation tests.
"""

from typing import Any


def print_eval_results(
    phase_name: str,
    tool_score: float,
    tool_reason: str,
    task_score: float,
    task_reason: str,
    capture: Any,
    token_usage: dict,
) -> None:
    """Print standardized evaluation results."""
    print(f"\n{'=' * 60}")
    print(f"{phase_name.upper()} EVALUATION RESULTS")
    print(f"{'=' * 60}")

    # Tool calls first
    print(f"\n{'-' * 40}")
    print("TOOL CALLS")
    print(f"{'-' * 40}")
    print(f"Total: {len(capture.calls)}")
    print(f"Sequence: {capture.names}")
    for i, call in enumerate(capture.calls):
        print(f"  {i + 1}. {call.name}({call.input_parameters})")

    # Tool correctness metric
    print(f"\n{'-' * 40}")
    print("TOOL CORRECTNESS")
    print(f"{'-' * 40}")
    print(f"Score: {tool_score}")
    print(f"Reason: {tool_reason}")

    # Task completion metric
    print(f"\n{'-' * 40}")
    print("TASK COMPLETION")
    print(f"{'-' * 40}")
    print(f"Score: {task_score}")
    print(f"Reason: {task_reason}")

    # Token usage
    print(f"\n{'-' * 40}")
    print("TOKEN USAGE")
    print(f"{'-' * 40}")
    print(f"  Input Tokens:  {token_usage.get('inputTokens', 'N/A')}")
    print(f"  Output Tokens: {token_usage.get('outputTokens', 'N/A')}")
    print(f"  Total Tokens:  {token_usage.get('totalTokens', 'N/A')}")

    print(f"\n{'=' * 60}")
