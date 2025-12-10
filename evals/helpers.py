"""
Helper functions for evaluation tests.
"""

from typing import Any


def print_eval_results(
    phase_name: str,
    prompt_chars: int,
    metric_score: float,
    metric_reason: str,
    capture: Any,
    token_usage: dict,
    metrics_summary: dict,
) -> None:
    """Print standardized evaluation results."""
    print(f"\n{'-' * 40}")
    print(f"{phase_name.upper()} PHASE EVALUATION")
    print(f"{'-' * 40}")
    print(f"\nSystem Prompt: {prompt_chars} chars")
    print(f"Score: {metric_score}")
    print(f"Reason: {metric_reason}")

    print(f"\nTool Calls ({len(capture.calls)} total): {capture.names}")
    for i, call in enumerate(capture.calls):
        print(f"  {i + 1}. {call.name}({call.input_parameters})")

    print(f"\n{'-' * 40}")
    print("TOKEN USAGE")
    print(f"{'-' * 40}")
    print(f"  Input Tokens:  {token_usage.get('inputTokens', 'N/A')}")
    print(f"  Output Tokens: {token_usage.get('outputTokens', 'N/A')}")
    print(f"  Total Tokens:  {token_usage.get('totalTokens', 'N/A')}")

    print(f"\n{'-' * 40}")
    print("EXECUTION STATS")
    print(f"{'-' * 40}")
    total_duration = metrics_summary.get("total_duration")
    avg_cycle = metrics_summary.get("average_cycle_time")
    print(f"  Duration:      {total_duration:.2f}s" if total_duration else "  Duration:      N/A")
    print(f"  Avg Cycle:     {avg_cycle:.2f}s" if avg_cycle else "  Avg Cycle:     N/A")
    print(f"\n{'-' * 40}")
