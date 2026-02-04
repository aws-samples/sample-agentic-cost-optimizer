/**
 * Configuration for AgentCore Online Evaluations
 */
export const EvalsConfig = {
  /**
   * Percentage of agent traces to sample for evaluation (0.01-100)
   */
  samplingPercentage: 100,

  /**
   * Minutes of inactivity after which a session is considered complete
   */
  sessionTimeoutMinutes: 5,

  /**
   * Built-in evaluators to apply during online evaluation
   */
  evaluators: [
    'Builtin.ToolSelectionAccuracy',
    'Builtin.ToolParameterAccuracy',
    'Builtin.Correctness',
    'Builtin.Helpfulness',
    'Builtin.Conciseness',
    'Builtin.InstructionFollowing',
    'Builtin.ResponseRelevance',
    'Builtin.Coherence',
    'Builtin.Faithfulness',
    'Builtin.GoalSuccessRate',
  ],

  /**
   * Default endpoint name for AgentCore Runtime
   */
  defaultEndpointName: 'DEFAULT',
} as const;

/**
 * Generate the evaluation config name based on environment
 */
export function getEvalsConfigName(environment: string): string {
  return `cost_optimizer_eval_${environment}`;
}
