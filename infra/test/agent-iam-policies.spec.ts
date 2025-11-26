import { App } from 'aws-cdk-lib';
import { describe, expect, it } from 'vitest';

import { Template } from 'aws-cdk-lib/assertions';

import { InfraStack } from '../lib/infra-stack';

describe('Agent IAM Policies', () => {
  const app = new App();
  const stack = new InfraStack(app, 'TestStack');
  const template = Template.fromStack(stack);

  describe('CloudWatch Logs Monitoring Policy', () => {
    it('should scope CloudWatch Logs access to Lambda log groups only', () => {
      const policies = template.findResources('AWS::IAM::Policy', {
        Properties: {
          PolicyName: 'MonitoringPolicy',
        },
      });

      const policyKey = Object.keys(policies)[0];
      const policy = policies[policyKey];
      const statements = policy.Properties.PolicyDocument.Statement;

      const logsStatement = statements.find((stmt: any) => stmt.Sid === 'CloudWatchLogsMonitoring');

      expect(logsStatement).toBeDefined();
      expect(logsStatement.Effect).toBe('Allow');

      const resource = logsStatement.Resource;
      const resourceString = JSON.stringify(resource);
      expect(resourceString).toContain('logs:*:*:log-group:/aws/lambda/*');
    });

    it('should not use wildcard for all CloudWatch Logs resources', () => {
      const policies = template.findResources('AWS::IAM::Policy', {
        Properties: {
          PolicyName: 'MonitoringPolicy',
        },
      });

      const policyKey = Object.keys(policies)[0];
      const policy = policies[policyKey];
      const statements = policy.Properties.PolicyDocument.Statement;

      const logsStatement = statements.find((stmt: any) => stmt.Sid === 'CloudWatchLogsMonitoring');

      expect(logsStatement.Resource).not.toContain('*');
    });

    it('should include required CloudWatch Logs actions', () => {
      const policies = template.findResources('AWS::IAM::Policy', {
        Properties: {
          PolicyName: 'MonitoringPolicy',
        },
      });

      const policyKey = Object.keys(policies)[0];
      const policy = policies[policyKey];
      const statements = policy.Properties.PolicyDocument.Statement;

      const logsStatement = statements.find((stmt: any) => stmt.Sid === 'CloudWatchLogsMonitoring');

      const requiredActions = ['logs:StartQuery', 'logs:GetLogEvents', 'logs:FilterLogEvents', 'logs:GetQueryResults'];

      requiredActions.forEach((action) => {
        expect(logsStatement.Action).toContain(action);
      });
    });
  });

  describe('Lambda Monitoring Policy', () => {
    it('should allow Lambda read-only monitoring actions', () => {
      const policies = template.findResources('AWS::IAM::Policy', {
        Properties: {
          PolicyName: 'MonitoringPolicy',
        },
      });

      const policyKey = Object.keys(policies)[0];
      const policy = policies[policyKey];
      const statements = policy.Properties.PolicyDocument.Statement;

      const lambdaStatement = statements.find((stmt: any) => stmt.Sid === 'LambdaMonitoring');

      expect(lambdaStatement).toBeDefined();
      expect(lambdaStatement.Effect).toBe('Allow');
      expect(lambdaStatement.Action).toContain('lambda:GetFunction');
      expect(lambdaStatement.Action).toContain('lambda:ListFunctions');
    });
  });
});
