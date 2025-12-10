"""
Helper functions for evaluation tests.
"""

from typing import Any


def print_eval_results(
    phase_name: str,
    prompt_chars: int,
    tool_score: float,
    tool_reason: str,
    task_score: float,
    task_reason: str,
    capture: Any,
    token_usage: dict,
    metrics_summary: dict,
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

    # Execution stats
    print(f"\n{'-' * 40}")
    print("EXECUTION STATS")
    print(f"{'-' * 40}")
    print(f"  System Prompt: {prompt_chars} chars")
    total_duration = metrics_summary.get("total_duration")
    avg_cycle = metrics_summary.get("average_cycle_time")
    print(f"  Duration:      {total_duration:.2f}s" if total_duration else "  Duration:      N/A")
    print(f"  Avg Cycle:     {avg_cycle:.2f}s" if avg_cycle else "  Avg Cycle:     N/A")
    print(f"\n{'=' * 60}")
