/**
 * Event status constants for Lambda and Step Functions
 * Used for tracking agent workflow lifecycle events
 */

export const EventStatus = {
  /**
   * Session has been initiated by Step Functions
   */
  SESSION_INITIATED: 'SESSION_INITIATED',

  /**
   * Lambda has started invoking the agent
   */
  AGENT_INVOCATION_STARTED: 'AGENT_INVOCATION_STARTED',

  /**
   * Lambda successfully invoked the agent
   */
  AGENT_INVOCATION_SUCCEEDED: 'AGENT_INVOCATION_SUCCEEDED',

  /**
   * Lambda failed to invoke the agent
   */
  AGENT_INVOCATION_FAILED: 'AGENT_INVOCATION_FAILED',

  /**
   * Agent background task completed (used by Step Functions for polling)
   */
  AGENT_BACKGROUND_TASK_COMPLETED: 'AGENT_BACKGROUND_TASK_COMPLETED',

  /**
   * Agent background task failed (used by Step Functions for polling)
   */
  AGENT_BACKGROUND_TASK_FAILED: 'AGENT_BACKGROUND_TASK_FAILED',
} as const;

export type EventStatusType = (typeof EventStatus)[keyof typeof EventStatus];
