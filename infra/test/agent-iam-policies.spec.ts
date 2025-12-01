import { describe, expect, it } from 'vitest';

import { createTestStack } from './setup';

describe('Agent IAM Policies', () => {
  const { template } = createTestStack();

  describe('CloudWatch Metrics Policy', () => {
    it('should allow CloudWatch Metrics read access', () => {
      const policies = template.findResources('AWS::IAM::Policy', {
        Properties: {
          PolicyName: 'MonitoringPolicy',
        },
      });

      const policyKey = Object.keys(policies)[0];
      const policy = policies[policyKey];
      const statements = policy.Properties.PolicyDocument.Statement;

      const metricsStatement = statements.find((stmt: any) => stmt.Sid === 'CloudWatchMetricsAccess');

      expect(metricsStatement).toBeDefined();
      expect(metricsStatement.Effect).toBe('Allow');
      expect(metricsStatement.Action).toContain('cloudwatch:GetMetricStatistics');
      expect(metricsStatement.Action).toContain('cloudwatch:ListMetrics');
      expect(metricsStatement.Resource).toEqual('*');
    });
  });

  describe('CloudWatch Logs Monitoring Policy', () => {
    it('should scope log access actions to Lambda log groups', () => {
      const policies = template.findResources('AWS::IAM::Policy', {
        Properties: {
          PolicyName: 'MonitoringPolicy',
        },
      });

      const policyKey = Object.keys(policies)[0];
      const policy = policies[policyKey];
      const statements = policy.Properties.PolicyDocument.Statement;

      const logsAccessStatement = statements.find((stmt: any) => stmt.Sid === 'CloudWatchLogsAccess');

      expect(logsAccessStatement).toBeDefined();
      expect(logsAccessStatement.Effect).toBe('Allow');
      expect(logsAccessStatement.Action).toContain('logs:StartQuery');
      expect(logsAccessStatement.Action).toContain('logs:GetLogEvents');
      expect(logsAccessStatement.Action).toContain('logs:FilterLogEvents');

      const resource = logsAccessStatement.Resource;
      const resourceString = JSON.stringify(resource);
      expect(resourceString).toContain('logs:*:*:log-group:/aws/lambda/*');
    });

    it('should allow StopQuery and GetQueryResults with wildcard resources', () => {
      const policies = template.findResources('AWS::IAM::Policy', {
        Properties: {
          PolicyName: 'MonitoringPolicy',
        },
      });

      const policyKey = Object.keys(policies)[0];
      const policy = policies[policyKey];
      const statements = policy.Properties.PolicyDocument.Statement;

      const queryResultsStatement = statements.find((stmt: any) => stmt.Sid === 'CloudWatchLogsQueryAccess');

      expect(queryResultsStatement).toBeDefined();
      expect(queryResultsStatement.Effect).toBe('Allow');
      expect(queryResultsStatement.Action).toContain('logs:StopQuery');
      expect(queryResultsStatement.Action).toContain('logs:GetQueryResults');
      expect(queryResultsStatement.Resource).toEqual('*');
    });

    it('should not include CloudWatch Metrics actions in Logs statements', () => {
      const policies = template.findResources('AWS::IAM::Policy', {
        Properties: {
          PolicyName: 'MonitoringPolicy',
        },
      });

      const policyKey = Object.keys(policies)[0];
      const policy = policies[policyKey];
      const statements = policy.Properties.PolicyDocument.Statement;

      const logsStatements = statements.filter(
        (stmt: any) => stmt.Sid === 'CloudWatchLogsAccess' || stmt.Sid === 'CloudWatchLogsQueryAccess',
      );

      logsStatements.forEach((stmt: any) => {
        const actions = Array.isArray(stmt.Action) ? stmt.Action : [stmt.Action];
        expect(actions).not.toContain('cloudwatch:GetMetricStatistics');
        expect(actions).not.toContain('cloudwatch:ListMetrics');
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
