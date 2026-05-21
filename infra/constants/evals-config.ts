import { BuiltinEvaluator } from 'aws-cdk-lib/aws-bedrockagentcore';

/**
 * Configuration for AgentCore Online Evaluations
 */
export const EvalsConfig = {
  /**
   * Built-in evaluators to apply during online evaluation
   */
  evaluators: [
    BuiltinEvaluator.TOOL_SELECTION_ACCURACY,
    BuiltinEvaluator.TOOL_PARAMETER_ACCURACY,
    BuiltinEvaluator.CORRECTNESS,
    BuiltinEvaluator.HELPFULNESS,
    BuiltinEvaluator.CONCISENESS,
    BuiltinEvaluator.INSTRUCTION_FOLLOWING,
    BuiltinEvaluator.RESPONSE_RELEVANCE,
    BuiltinEvaluator.COHERENCE,
    BuiltinEvaluator.FAITHFULNESS,
    BuiltinEvaluator.GOAL_SUCCESS_RATE,
  ],
} as const;

/**
 * Generate the evaluation config name based on environment
 */
export function getEvalsConfigName(environment: string): string {
  return `cost_optimizer_eval_${environment}`;
}
