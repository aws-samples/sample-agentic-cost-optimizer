class EventStatus:
    """Event status constants for agent lifecycle events

    Event Flow:
    1. SESSION_INITIATED - Step Function starts workflow
    2. AGENT_INVOCATION_STARTED - Lambda invoker invokes AgentCore runtime
    3. AGENT_INVOCATION_SUCCEEDED/FAILED - AgentCore responded successfully / AgentCore invocation failed
    4. AGENT_RUNTIME_INVOKE_STARTED - Agent entrypoint starts processing request inside AgentCore
    5. AGENT_RUNTIME_INVOKE_FAILED - Agent entrypoint fails before starting background task
    6. AGENT_BACKGROUND_TASK_STARTED - Agent starts fire-and-forget background processing
    7. AGENT_BACKGROUND_TASK_COMPLETED/FAILED - Background processing finishes
    """

    # Session lifecycle
    SESSION_INITIATED = "SESSION_INITIATED"

    # Lambda invoker → AgentCore communication
    AGENT_INVOCATION_STARTED = "AGENT_INVOCATION_STARTED"
    AGENT_INVOCATION_SUCCEEDED = "AGENT_INVOCATION_SUCCEEDED"
    AGENT_INVOCATION_FAILED = "AGENT_INVOCATION_FAILED"

    # Agent invoke and background task
    AGENT_RUNTIME_INVOKE_STARTED = "AGENT_RUNTIME_INVOKE_STARTED"
    AGENT_RUNTIME_INVOKE_FAILED = "AGENT_RUNTIME_INVOKE_FAILED"
    AGENT_BACKGROUND_TASK_STARTED = "AGENT_BACKGROUND_TASK_STARTED"
    AGENT_BACKGROUND_TASK_COMPLETED = "AGENT_BACKGROUND_TASK_COMPLETED"
    AGENT_BACKGROUND_TASK_FAILED = "AGENT_BACKGROUND_TASK_FAILED"
