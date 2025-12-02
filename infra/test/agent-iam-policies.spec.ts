import { beforeEach, describe, expect, it } from 'vitest';

import { type PolicyResource, type PolicyStatementJson, createTestStack } from './setup';

describe('Agent IAM Policies', () => {
  const { template } = createTestStack();
  let monitoringPolicy: PolicyResource;
  let statements: PolicyStatementJson[];

  beforeEach(() => {
    const policies = template.findResources('AWS::IAM::Policy', {
      Properties: { PolicyName: 'MonitoringPolicy' },
    });
    monitoringPolicy = Object.values(policies)[0] as PolicyResource;
    statements = monitoringPolicy.Properties.PolicyDocument.Statement;
  });

  describe('CloudWatch Metrics Policy', () => {
    it('should allow CloudWatch Metrics read access', () => {
      const metricsStatement = statements.find((stmt) => stmt.Sid === 'CloudWatchMetricsAccess');

      expect(metricsStatement).toBeDefined();
      expect(metricsStatement!.Effect).toBe('Allow');
      expect(metricsStatement!.Action).toContain('cloudwatch:GetMetricStatistics');
      expect(metricsStatement!.Action).toContain('cloudwatch:ListMetrics');
      expect(metricsStatement!.Resource).toEqual('*');
    });
  });

  describe('CloudWatch Logs Monitoring Policy', () => {
    it('should scope log access actions to Lambda log groups', () => {
      const logsAccessStatement = statements.find((stmt) => stmt.Sid === 'CloudWatchLogsAccess');

      expect(logsAccessStatement).toBeDefined();
      expect(logsAccessStatement!.Effect).toBe('Allow');
      expect(logsAccessStatement!.Action).toContain('logs:StartQuery');
      expect(logsAccessStatement!.Action).toContain('logs:GetLogEvents');
      expect(logsAccessStatement!.Action).toContain('logs:FilterLogEvents');

      const resource = logsAccessStatement!.Resource;
      const resourceString = JSON.stringify(resource);
      expect(resourceString).toContain('logs:*:*:log-group:/aws/lambda/*');
    });

    it('should allow StopQuery and GetQueryResults with wildcard resources', () => {
      const queryResultsStatement = statements.find((stmt) => stmt.Sid === 'CloudWatchLogsQueryAccess');

      expect(queryResultsStatement).toBeDefined();
      expect(queryResultsStatement!.Effect).toBe('Allow');
      expect(queryResultsStatement!.Action).toContain('logs:StopQuery');
      expect(queryResultsStatement!.Action).toContain('logs:GetQueryResults');
      expect(queryResultsStatement!.Resource).toEqual('*');
    });

    it('should not include CloudWatch Metrics actions in Logs statements', () => {
      const logsStatements = statements.filter((stmt) => stmt.Sid === 'CloudWatchLogsAccess' || stmt.Sid === 'CloudWatchLogsQueryAccess');

      logsStatements.forEach((stmt) => {
        const actions = Array.isArray(stmt.Action) ? stmt.Action : [stmt.Action];
        expect(actions).not.toContain('cloudwatch:GetMetricStatistics');
        expect(actions).not.toContain('cloudwatch:ListMetrics');
      });
    });
  });

  describe('Lambda Monitoring Policy', () => {
    it('should allow Lambda read-only monitoring actions', () => {
      const lambdaStatement = statements.find((stmt) => stmt.Sid === 'LambdaMonitoring');

      expect(lambdaStatement).toBeDefined();
      expect(lambdaStatement!.Effect).toBe('Allow');
      expect(lambdaStatement!.Action).toContain('lambda:GetFunction');
      expect(lambdaStatement!.Action).toContain('lambda:ListFunctions');
    });
  });
});
