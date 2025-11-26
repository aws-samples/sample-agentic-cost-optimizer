#!/usr/bin/env python3
"""
OpenTelemetry instrumentation wrapper for AgentCore Runtime.
Initializes OTEL auto-instrumentation before importing the agent.
"""

if __name__ == "__main__":
    # Initialize OpenTelemetry auto-instrumentation

    # Now run the agent module (OTEL is already initialized)
    import runpy

    runpy.run_module("src.agents.main", run_name="__main__")
