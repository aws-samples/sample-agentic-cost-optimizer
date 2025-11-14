import { App } from 'aws-cdk-lib';
import { describe, expect, it } from 'vitest';

import { Template } from 'aws-cdk-lib/assertions';

import { InfraStack } from '../lib/infra-stack';

describe('EventBridge Rules', () => {
  const app = new App();
  const stack = new InfraStack(app, 'TestStack');
  const template = Template.fromStack(stack);

  describe('Manual Trigger Rule', () => {
    it('should be configured with correct event pattern', () => {
      template.hasResourceProperties('AWS::Events::Rule', {
        EventPattern: {
          source: ['manual-trigger'],
          'detail-type': ['execute-agent'],
        },
        Description: 'Rule to trigger agent workflow via manual EventBridge events',
      });
    });

    it('should have a target configured', () => {
      const rules = template.findResources('AWS::Events::Rule', {
        Properties: {
          EventPattern: {
            source: ['manual-trigger'],
          },
        },
      });

      const ruleKey = Object.keys(rules)[0];
      const rule = rules[ruleKey];
      expect(rule.Properties.Targets).toBeDefined();
      expect(rule.Properties.Targets).toHaveLength(1);
    });
  });

  describe('Scheduled Trigger Rule', () => {
    it('should be configured to run daily at 6am UTC', () => {
      template.hasResourceProperties('AWS::Events::Rule', {
        ScheduleExpression: 'cron(0 6 * * ? *)',
        Description: 'Rule to trigger agent workflow daily at 6am UTC',
      });
    });

    it('should have a target configured', () => {
      const rules = template.findResources('AWS::Events::Rule', {
        Properties: {
          ScheduleExpression: 'cron(0 6 * * ? *)',
        },
      });

      const ruleKey = Object.keys(rules)[0];
      const rule = rules[ruleKey];
      expect(rule.Properties.Targets).toBeDefined();
      expect(rule.Properties.Targets).toHaveLength(1);
    });
  });

  describe('EventBridge Rules Count', () => {
    it('should have exactly 2 EventBridge rules', () => {
      const rules = template.findResources('AWS::Events::Rule');
      expect(Object.keys(rules)).toHaveLength(2);
    });
  });
});
