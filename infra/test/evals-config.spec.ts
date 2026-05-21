import { describe, expect, it } from 'vitest';

import { BuiltinEvaluator } from 'aws-cdk-lib/aws-bedrockagentcore';

import { EvalsConfig, getEvalsConfigName } from '../constants/evals-config';

describe('Evals Config', () => {
  describe('getEvalsConfigName', () => {
    it('should return correct pattern for dev environment', () => {
      expect(getEvalsConfigName('dev')).toBe('cost_optimizer_eval_dev');
    });

    it('should return correct pattern for prod environment', () => {
      expect(getEvalsConfigName('prod')).toBe('cost_optimizer_eval_prod');
    });
  });

  describe('EvalsConfig.evaluators', () => {
    it('should have 10 built-in evaluators', () => {
      expect(EvalsConfig.evaluators).toHaveLength(10);
    });

    it('should include all required builtin evaluators', () => {
      expect(EvalsConfig.evaluators).toEqual([
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
      ]);
    });
  });
});
