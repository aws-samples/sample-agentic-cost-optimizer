import { describe, expect, it } from 'vitest';

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

  describe('EvalsConfig constants', () => {
    it('should have samplingPercentage set to 100', () => {
      expect(EvalsConfig.samplingPercentage).toBe(100);
    });

    it('should have sessionTimeoutMinutes set to 5', () => {
      expect(EvalsConfig.sessionTimeoutMinutes).toBe(5);
    });

    it('should have 10 built-in evaluators', () => {
      expect(EvalsConfig.evaluators).toHaveLength(10);
    });

    it('should include all required evaluators', () => {
      const expectedEvaluators = [
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
      ];
      expect(EvalsConfig.evaluators).toEqual(expectedEvaluators);
    });

    it('should have defaultEndpointName set to DEFAULT', () => {
      expect(EvalsConfig.defaultEndpointName).toBe('DEFAULT');
    });
  });
});
