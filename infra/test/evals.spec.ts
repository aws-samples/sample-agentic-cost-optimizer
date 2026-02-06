import { App, Stack } from 'aws-cdk-lib';
import { beforeEach, describe, expect, it } from 'vitest';

import { Match, Template } from 'aws-cdk-lib/assertions';

import { Agent } from '../lib/agent';
import { Evals } from '../lib/evals';
import { InfraStack } from '../lib/infra-stack';

/**
 * Creates a test stack with Agent and Evals constructs for testing
 */
function createEvalsTestStack() {
  const app = new App();
  const stack = new Stack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });

  const agent = new Agent(stack, 'TestAgent', {
    agentRuntimeName: 'testRuntime_dev_v1',
    description: 'Test agent for evals testing',
    environment: 'dev',
    modelId: 'anthropic.claude-sonnet-4-5-20250929-v1:0',
    inferenceProfileRegion: 'us',
  });

  const evals = new Evals(stack, 'TestEvals', {
    agent,
    environment: 'dev',
  });

  const template = Template.fromStack(stack);

  return { app, stack, agent, evals, template };
}

describe('Evals Construct', () => {
  let template: Template;

  beforeEach(() => {
    const testStack = createEvalsTestStack();
    template = testStack.template;
  });

  describe('Execution Role Trust Policy', () => {
    it('should create execution role with bedrock-agentcore.amazonaws.com trust policy', () => {
      template.hasResourceProperties('AWS::IAM::Role', {
        AssumeRolePolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: 'sts:AssumeRole',
              Effect: 'Allow',
              Principal: {
                Service: 'bedrock-agentcore.amazonaws.com',
              },
            }),
          ]),
        },
      });
    });

    it('should include aws:SourceAccount condition in trust policy', () => {
      template.hasResourceProperties('AWS::IAM::Role', {
        AssumeRolePolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Condition: Match.objectLike({
                StringEquals: Match.objectLike({
                  'aws:SourceAccount': '123456789012',
                }),
              }),
            }),
          ]),
        },
      });
    });

    it('should include aws:ResourceAccount condition in trust policy', () => {
      template.hasResourceProperties('AWS::IAM::Role', {
        AssumeRolePolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Condition: Match.objectLike({
                StringEquals: Match.objectLike({
                  'aws:ResourceAccount': '123456789012',
                }),
              }),
            }),
          ]),
        },
      });
    });

    it('should include ArnLike condition for evaluator and online-evaluation-config', () => {
      // Verify the role has ArnLike condition - checking the structure exists
      template.hasResourceProperties('AWS::IAM::Role', {
        AssumeRolePolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Condition: Match.objectLike({
                ArnLike: Match.objectLike({
                  'aws:SourceArn': Match.anyValue(),
                }),
              }),
            }),
          ]),
        },
      });
    });
  });

  describe('Execution Role CloudWatch Logs Read Permissions', () => {
    it('should have CloudWatch Logs read permissions with correct actions', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Sid: 'CloudWatchLogsRead',
              Effect: 'Allow',
              Action: ['logs:DescribeLogGroups', 'logs:GetQueryResults', 'logs:StartQuery'],
              Resource: '*',
            }),
          ]),
        },
      });
    });
  });

  describe('Execution Role CloudWatch Logs Write Permissions', () => {
    it('should have CloudWatch Logs write permissions for evaluations log group', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Sid: 'CloudWatchLogsWrite',
              Effect: 'Allow',
              Action: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
            }),
          ]),
        },
      });
    });

    it('should scope CloudWatch Logs write to /aws/bedrock-agentcore/evaluations/*', () => {
      // Find the policy with CloudWatchLogsWrite statement and verify resource pattern
      const policies = template.findResources('AWS::IAM::Policy');
      const policyWithLogsWrite = Object.values(policies).find((policy) => {
        const statements = (policy as { Properties: { PolicyDocument: { Statement: Array<{ Sid?: string }> } } }).Properties?.PolicyDocument
          ?.Statement;
        return statements?.some((stmt) => stmt.Sid === 'CloudWatchLogsWrite');
      });

      expect(policyWithLogsWrite).toBeDefined();
      const statements = (
        policyWithLogsWrite as { Properties: { PolicyDocument: { Statement: Array<{ Sid?: string; Resource?: unknown }> } } }
      ).Properties.PolicyDocument.Statement;
      const logsWriteStmt = statements.find((stmt) => stmt.Sid === 'CloudWatchLogsWrite');
      const resourceStr = JSON.stringify(logsWriteStmt?.Resource);
      expect(resourceStr).toContain('/aws/bedrock-agentcore/evaluations/*');
    });
  });

  describe('Execution Role CloudWatch Index Policy Permissions', () => {
    it('should have CloudWatch index policy permissions', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Sid: 'CloudWatchIndexPolicy',
              Effect: 'Allow',
              Action: ['logs:DescribeIndexPolicies', 'logs:PutIndexPolicy'],
            }),
          ]),
        },
      });
    });

    it('should scope CloudWatch index policy to aws/spans log group', () => {
      // Find the policy with CloudWatchIndexPolicy statement and verify resource pattern
      const policies = template.findResources('AWS::IAM::Policy');
      const policyWithIndexPolicy = Object.values(policies).find((policy) => {
        const statements = (policy as { Properties: { PolicyDocument: { Statement: Array<{ Sid?: string }> } } }).Properties?.PolicyDocument
          ?.Statement;
        return statements?.some((stmt) => stmt.Sid === 'CloudWatchIndexPolicy');
      });

      expect(policyWithIndexPolicy).toBeDefined();
      const statements = (
        policyWithIndexPolicy as { Properties: { PolicyDocument: { Statement: Array<{ Sid?: string; Resource?: unknown }> } } }
      ).Properties.PolicyDocument.Statement;
      const indexPolicyStmt = statements.find((stmt) => stmt.Sid === 'CloudWatchIndexPolicy');
      const resourceStr = JSON.stringify(indexPolicyStmt?.Resource);
      expect(resourceStr).toContain('log-group:aws/spans');
    });
  });

  describe('Execution Role Bedrock Model Permissions', () => {
    it('should have Bedrock model invocation permissions', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Sid: 'BedrockModelInvocation',
              Effect: 'Allow',
              Action: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
              Resource: '*',
            }),
          ]),
        },
      });
    });
  });

  describe('AwsCustomResource Configuration', () => {
    it('should create AwsCustomResource with Custom::BedrockAgentCoreOnlineEvaluation type', () => {
      template.hasResource('Custom::BedrockAgentCoreOnlineEvaluation', {});
    });

    it('should configure onCreate with CreateOnlineEvaluationConfig action', () => {
      const resources = template.findResources('Custom::BedrockAgentCoreOnlineEvaluation');
      expect(Object.keys(resources).length).toBeGreaterThan(0);

      // The Create property is a Fn::Join that contains the SDK call configuration as JSON
      const resource = Object.values(resources)[0] as { Properties?: { Create?: unknown } };
      expect(resource.Properties?.Create).toBeDefined();
      const createStr = JSON.stringify(resource.Properties!.Create);
      expect(createStr).toContain('bedrock-agentcore-control');
      expect(createStr).toContain('CreateOnlineEvaluationConfig');
    });

    it('should configure onUpdate with UpdateOnlineEvaluationConfig action', () => {
      const resources = template.findResources('Custom::BedrockAgentCoreOnlineEvaluation');
      const resource = Object.values(resources)[0] as { Properties?: { Update?: unknown } };
      expect(resource.Properties?.Update).toBeDefined();
      const updateStr = JSON.stringify(resource.Properties!.Update);
      expect(updateStr).toContain('bedrock-agentcore-control');
      expect(updateStr).toContain('UpdateOnlineEvaluationConfig');
    });

    it('should configure onDelete with DeleteOnlineEvaluationConfig action', () => {
      const resources = template.findResources('Custom::BedrockAgentCoreOnlineEvaluation');
      const resource = Object.values(resources)[0] as { Properties?: { Delete?: unknown } };
      expect(resource.Properties?.Delete).toBeDefined();
      const deleteStr = JSON.stringify(resource.Properties!.Delete);
      expect(deleteStr).toContain('bedrock-agentcore-control');
      expect(deleteStr).toContain('DeleteOnlineEvaluationConfig');
    });
  });

  describe('AwsCustomResource Policy - Admin Permissions', () => {
    it('should have bedrock-agentcore admin permissions', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Sid: 'BedrockAgentCoreAdmin',
              Effect: 'Allow',
              Action: Match.arrayWith([
                'bedrock-agentcore:CreateOnlineEvaluationConfig',
                'bedrock-agentcore:GetOnlineEvaluationConfig',
                'bedrock-agentcore:UpdateOnlineEvaluationConfig',
                'bedrock-agentcore:DeleteOnlineEvaluationConfig',
                'bedrock-agentcore:ListOnlineEvaluationConfigs',
              ]),
              Resource: '*',
            }),
          ]),
        },
      });
    });
  });

  describe('AwsCustomResource Policy - PassRole Permission', () => {
    it('should have iam:PassRole permission for execution role', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Sid: 'PassRole',
              Effect: 'Allow',
              Action: 'iam:PassRole',
            }),
          ]),
        },
      });
    });
  });

  describe('AwsCustomResource Policy - CloudWatch Index Permissions', () => {
    it('should have CloudWatch index permissions for custom resource', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Sid: 'CloudWatchIndexPermissions',
              Effect: 'Allow',
              Action: Match.arrayWith(['logs:DescribeIndexPolicies', 'logs:PutIndexPolicy', 'logs:CreateLogGroup']),
              Resource: '*',
            }),
          ]),
        },
      });
    });
  });
});

describe('InfraStack Conditional Evals Creation', () => {
  describe('when enableEvals is true', () => {
    it('should create Evals construct', () => {
      const app = new App();
      const stack = new InfraStack(app, 'TestStack', {
        environment: 'dev',
        runtimeVersion: 'v2',
        enableScheduledTrigger: false,
        enableManualTrigger: false,
        enableEvals: true,
      });
      const template = Template.fromStack(stack);

      // Verify the Custom Resource for Evals is created
      template.hasResource('Custom::BedrockAgentCoreOnlineEvaluation', {});
    });

    it('should expose evals property on stack', () => {
      const app = new App();
      const stack = new InfraStack(app, 'TestStack', {
        environment: 'dev',
        runtimeVersion: 'v2',
        enableScheduledTrigger: false,
        enableManualTrigger: false,
        enableEvals: true,
      });

      expect(stack.evals).toBeDefined();
    });

    it('should create CfnOutputs for evaluation config', () => {
      const app = new App();
      const stack = new InfraStack(app, 'TestStack', {
        environment: 'dev',
        runtimeVersion: 'v2',
        enableScheduledTrigger: false,
        enableManualTrigger: false,
        enableEvals: true,
      });
      const template = Template.fromStack(stack);

      // Verify CfnOutputs for EvaluationConfigId and EvaluationConfigArn exist
      const outputs = template.findOutputs('*');
      expect(Object.keys(outputs).some((key) => key.includes('EvaluationConfigId'))).toBe(true);
      expect(Object.keys(outputs).some((key) => key.includes('EvaluationConfigArn'))).toBe(true);
    });
  });

  describe('when enableEvals is false', () => {
    it('should NOT create Evals construct', () => {
      const app = new App();
      const stack = new InfraStack(app, 'TestStack', {
        environment: 'dev',
        runtimeVersion: 'v2',
        enableScheduledTrigger: false,
        enableManualTrigger: false,
        enableEvals: false,
      });
      const template = Template.fromStack(stack);

      // Verify the Custom Resource for Evals is NOT created
      const resources = template.findResources('Custom::BedrockAgentCoreOnlineEvaluation');
      expect(Object.keys(resources).length).toBe(0);
    });

    it('should have undefined evals property on stack', () => {
      const app = new App();
      const stack = new InfraStack(app, 'TestStack', {
        environment: 'dev',
        runtimeVersion: 'v2',
        enableScheduledTrigger: false,
        enableManualTrigger: false,
        enableEvals: false,
      });

      expect(stack.evals).toBeUndefined();
    });

    it('should NOT create CfnOutputs for evaluation config', () => {
      const app = new App();
      const stack = new InfraStack(app, 'TestStack', {
        environment: 'dev',
        runtimeVersion: 'v2',
        enableScheduledTrigger: false,
        enableManualTrigger: false,
        enableEvals: false,
      });
      const template = Template.fromStack(stack);

      // Verify CfnOutputs for EvaluationConfigId and EvaluationConfigArn do NOT exist
      const outputs = template.findOutputs('*');
      expect(Object.keys(outputs).some((key) => key.includes('EvaluationConfigId'))).toBe(false);
      expect(Object.keys(outputs).some((key) => key.includes('EvaluationConfigArn'))).toBe(false);
    });
  });
});
