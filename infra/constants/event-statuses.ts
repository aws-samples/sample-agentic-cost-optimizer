/**
 * Event status constants for Lambda and Step Functions
 * Used for tracking agent workflow lifecycle events
 *
 * Event Flow:
 * 1. SESSION_INITIATED - Step Function starts workflow
 * 2. AGENT_INVOCATION_STARTED - Lambda invoker invokes AgentCore runtime
 * 3. AGENT_INVOCATION_SUCCEEDED/FAILED - AgentCore responded successfully / AgentCore invocation failed
 * 4. AGENT_RUNTIME_INVOKE_STARTED - Agent entrypoint starts processing request inside AgentCore
 * 5. AGENT_RUNTIME_INVOKE_FAILED - Agent entrypoint fails before starting background task
 * 6. AGENT_BACKGROUND_TASK_STARTED - Agent starts fire-and-forget background processing
 * 7. AGENT_BACKGROUND_TASK_COMPLETED/FAILED - Background processing finishes (Step Function polls for these)
 */

export const EventStatus = {
  /**
   * Session has been initiated by Step Functions
   */
  SESSION_INITIATED: 'SESSION_INITIATED',

  /**
   * Lambda invoker has invoked AgentCore runtime
   */
  AGENT_INVOCATION_STARTED: 'AGENT_INVOCATION_STARTED',

  /**
   * AgentCore responded successfully
   */
  AGENT_INVOCATION_SUCCEEDED: 'AGENT_INVOCATION_SUCCEEDED',

  /**
   * AgentCore invocation failed
   */
  AGENT_INVOCATION_FAILED: 'AGENT_INVOCATION_FAILED',

  /**
   * Agent background task completed successfully (Step Function polls for this)
   */
  AGENT_BACKGROUND_TASK_COMPLETED: 'AGENT_BACKGROUND_TASK_COMPLETED',

  /**
   * Agent background task failed (Step Function polls for this)
   */
  AGENT_BACKGROUND_TASK_FAILED: 'AGENT_BACKGROUND_TASK_FAILED',
} as const;

export type EventStatusType = (typeof EventStatus)[keyof typeof EventStatus];
