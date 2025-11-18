/**
 * Event status constants used by Step Functions workflow
 *
 * The Step Function polls DynamoDB for these statuses to determine when
 * the agent background task has completed or failed.
 *
 * Note: Other event statuses (SESSION_INITIATED, AGENT_RUNTIME_INVOCATION_STARTED, etc.)
 * are defined in Python at src/shared/event_statuses.py and used by Lambda functions.
 */

export const EventStatus = {
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
