import { beforeEach, describe, expect, it } from 'vitest';

import { createTestStack } from './setup';

interface EventBridgeRule {
  Properties: {
    EventPattern?: {
      source: string[];
      'detail-type'?: string[];
    };
    ScheduleExpression?: string;
    Description: string;
    Targets: Array<{
      InputTransformer?: {
        InputPathsMap: Record<string, string>;
        InputTemplate: string;
      };
    }>;
  };
}

describe('EventBridge Rules', () => {
  const { template } = createTestStack();

  describe('Manual Trigger Rule', () => {
    let manualRule: EventBridgeRule;

    beforeEach(() => {
      const rules = template.findResources('AWS::Events::Rule', {
        Properties: {
          EventPattern: {
            source: ['manual-trigger'],
          },
        },
      });
      manualRule = Object.values(rules)[0] as EventBridgeRule;
    });

    it('should be configured with correct event pattern', () => {
      expect(manualRule.Properties.EventPattern).toEqual({
        source: ['manual-trigger'],
        'detail-type': ['execute-agent'],
      });
      expect(manualRule.Properties.Description).toBe('Rule to trigger agent workflow via manual EventBridge events');
    });

    it('should have a target configured', () => {
      expect(manualRule.Properties.Targets).toBeDefined();
      expect(manualRule.Properties.Targets).toHaveLength(1);
    });
  });

  describe('Scheduled Trigger Rule', () => {
    let scheduledRule: EventBridgeRule;

    beforeEach(() => {
      const rules = template.findResources('AWS::Events::Rule', {
        Properties: {
          ScheduleExpression: 'cron(0 6 * * ? *)',
        },
      });
      scheduledRule = Object.values(rules)[0] as EventBridgeRule;
    });

    it('should be configured to run daily at 6am UTC', () => {
      expect(scheduledRule.Properties.ScheduleExpression).toBe('cron(0 6 * * ? *)');
      expect(scheduledRule.Properties.Description).toBe('Rule to trigger agent workflow daily at 6am UTC');
    });

    it('should have a target configured', () => {
      expect(scheduledRule.Properties.Targets).toBeDefined();
      expect(scheduledRule.Properties.Targets).toHaveLength(1);
    });

    it('should use event-id for session_id to meet AgentCore 33+ character requirement', () => {
      const target = scheduledRule.Properties.Targets[0];

      expect(target.InputTransformer).toBeDefined();
      expect(target.InputTransformer!.InputPathsMap).toHaveProperty('id');
      expect(target.InputTransformer!.InputPathsMap.id).toBe('$.id');
      expect(target.InputTransformer!.InputTemplate).toContain('"session_id":<id>');
    });
  });

  describe('EventBridge Rules Count', () => {
    it('should have exactly 2 EventBridge rules when enableManualTrigger is true', () => {
      const rules = template.findResources('AWS::Events::Rule');
      expect(Object.keys(rules)).toHaveLength(2);
    });

    it('should have exactly 1 EventBridge rule when enableManualTrigger is false', () => {
      const { template: prodTemplate } = createTestStack(false);
      const rules = prodTemplate.findResources('AWS::Events::Rule');
      expect(Object.keys(rules)).toHaveLength(1);
    });

    it('should not create manual trigger rule when enableManualTrigger is false', () => {
      const { template: prodTemplate } = createTestStack(false);
      const manualRules = prodTemplate.findResources('AWS::Events::Rule', {
        Properties: {
          EventPattern: {
            source: ['manual-trigger'],
          },
        },
      });
      expect(Object.keys(manualRules)).toHaveLength(0);
    });
  });
});
