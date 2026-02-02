import { Stack } from 'aws-cdk-lib';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

import { Effect, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { AwsCustomResource, AwsCustomResourcePolicy, PhysicalResourceId, PhysicalResourceIdReference } from 'aws-cdk-lib/custom-resources';

import { EvalsConfig, getEvalsConfigName } from '../constants/evals-config';
import { Agent } from './agent';

export interface EvalsProps {
  /**
   * The Agent construct to evaluate
   */
  agent: Agent;

  /**
   * Environment name (used in config naming)
   */
  environment: string;
}

/**
 * CDK construct that creates an AgentCore Online Evaluation configuration.
 *
 * This is a temporary implementation using AwsCustomResource to call the
 * bedrock-agentcore-control API directly. It will be replaced by the L2
 * construct once @aws-cdk/aws-bedrock-agentcore-alpha is published.
 */
export class Evals extends Construct {
  public readonly executionRole: Role;
  public readonly configId: string;
  public readonly configArn: string;

  constructor(scope: Construct, id: string, props: EvalsProps) {
    super(scope, id);

    const { agent, environment } = props;
    const stack = Stack.of(this);

    const agentRuntimeId = agent.runtime.agentRuntimeId;
    const agentRuntimeName = agent.runtimeName;
    const runtimeEndpointName = EvalsConfig.defaultEndpointName;

    // CloudWatch Logs data source derived from Agent runtime
    const traceLogGroupName = `/aws/bedrock-agentcore/runtimes/${agentRuntimeId}-${runtimeEndpointName}`;
    const traceServiceName = `${agentRuntimeName}.${runtimeEndpointName}`;

    this.executionRole = new Role(this, 'ExecutionRole', {
      assumedBy: new ServicePrincipal('bedrock-agentcore.amazonaws.com', {
        conditions: {
          StringEquals: {
            'aws:SourceAccount': stack.account,
            'aws:ResourceAccount': stack.account,
          },
          ArnLike: {
            'aws:SourceArn': [
              `arn:${stack.partition}:bedrock-agentcore:${stack.region}:${stack.account}:evaluator/*`,
              `arn:${stack.partition}:bedrock-agentcore:${stack.region}:${stack.account}:online-evaluation-config/*`,
            ],
          },
        },
      }),
      description: 'Execution role for AgentCore Online Evaluations',
    });

    this.executionRole.addToPolicy(
      new PolicyStatement({
        sid: 'CloudWatchLogsRead',
        effect: Effect.ALLOW,
        actions: ['logs:DescribeLogGroups', 'logs:GetQueryResults', 'logs:StartQuery'],
        resources: ['*'],
      }),
    );

    this.executionRole.addToPolicy(
      new PolicyStatement({
        sid: 'CloudWatchLogsWrite',
        effect: Effect.ALLOW,
        actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
        resources: [`arn:${stack.partition}:logs:${stack.region}:${stack.account}:log-group:/aws/bedrock-agentcore/evaluations/*`],
      }),
    );

    this.executionRole.addToPolicy(
      new PolicyStatement({
        sid: 'CloudWatchIndexPolicy',
        effect: Effect.ALLOW,
        actions: ['logs:DescribeIndexPolicies', 'logs:PutIndexPolicy'],
        resources: [`arn:${stack.partition}:logs:${stack.region}:${stack.account}:log-group:aws/spans`],
      }),
    );

    this.executionRole.addToPolicy(
      new PolicyStatement({
        sid: 'BedrockModelInvocation',
        effect: Effect.ALLOW,
        actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
        resources: ['*'],
      }),
    );

    const evaluatorConfigs = EvalsConfig.evaluators.map((evaluatorId) => ({ evaluatorId }));
    const evaluationConfigName = getEvalsConfigName(environment);

    const evaluationConfig = {
      onlineEvaluationConfigName: evaluationConfigName,
      evaluators: evaluatorConfigs,
      dataSourceConfig: {
        cloudWatchLogs: {
          logGroupNames: [traceLogGroupName],
          serviceNames: [traceServiceName],
        },
      },
      evaluationExecutionRoleArn: this.executionRole.roleArn,
      enableOnCreate: true,
      rule: {
        samplingConfig: {
          samplingPercentage: EvalsConfig.samplingPercentage,
        },
        sessionConfig: {
          sessionTimeoutMinutes: EvalsConfig.sessionTimeoutMinutes,
        },
      },
      description: `Online evaluation config for ${environment} environment`,
    };

    const evaluationConfigResource = new AwsCustomResource(this, 'Resource', {
      resourceType: 'Custom::BedrockAgentCoreOnlineEvaluation',
      installLatestAwsSdk: true,
      onCreate: {
        service: 'bedrock-agentcore-control',
        action: 'CreateOnlineEvaluationConfig',
        parameters: evaluationConfig,
        physicalResourceId: PhysicalResourceId.fromResponse('onlineEvaluationConfigId'),
      },
      onUpdate: {
        service: 'bedrock-agentcore-control',
        action: 'UpdateOnlineEvaluationConfig',
        parameters: {
          onlineEvaluationConfigId: new PhysicalResourceIdReference(),
          evaluators: evaluatorConfigs,
          rule: evaluationConfig.rule,
          description: evaluationConfig.description,
        },
        physicalResourceId: PhysicalResourceId.fromResponse('onlineEvaluationConfigId'),
      },
      onDelete: {
        service: 'bedrock-agentcore-control',
        action: 'DeleteOnlineEvaluationConfig',
        parameters: {
          onlineEvaluationConfigId: new PhysicalResourceIdReference(),
        },
      },
      policy: AwsCustomResourcePolicy.fromStatements([
        new PolicyStatement({
          sid: 'BedrockAgentCoreAdmin',
          effect: Effect.ALLOW,
          actions: [
            'bedrock-agentcore:CreateOnlineEvaluationConfig',
            'bedrock-agentcore:GetOnlineEvaluationConfig',
            'bedrock-agentcore:UpdateOnlineEvaluationConfig',
            'bedrock-agentcore:DeleteOnlineEvaluationConfig',
            'bedrock-agentcore:ListOnlineEvaluationConfigs',
          ],
          resources: ['*'],
        }),
        new PolicyStatement({
          sid: 'PassRole',
          effect: Effect.ALLOW,
          actions: ['iam:PassRole'],
          resources: [this.executionRole.roleArn],
        }),
        new PolicyStatement({
          sid: 'CloudWatchIndexPermissions',
          effect: Effect.ALLOW,
          actions: ['logs:DescribeIndexPolicies', 'logs:PutIndexPolicy', 'logs:CreateLogGroup'],
          resources: ['*'],
        }),
      ]),
    });

    this.configId = evaluationConfigResource.getResponseField('onlineEvaluationConfigId');
    this.configArn = evaluationConfigResource.getResponseField('onlineEvaluationConfigArn');

    this.applyNagSuppressions(stack, evaluationConfigResource);
  }

  /**
   * Apply CDK Nag suppressions for known security findings.
   *
   * Suppressed rules:
   * - AwsSolutions-IAM5: Wildcard permissions for dynamic resources (CloudWatch Logs, Bedrock models)
   * - AwsSolutions-IAM4: AWS managed policy (AWSLambdaBasicExecutionRole) for AwsCustomResource Lambda
   * - AwsSolutions-L1: Lambda runtime managed by CDK AwsCustomResource construct
   *
   * The AwsCustomResource creates a singleton Lambda at the stack level with a deterministic ID
   * (AWS679f53fac002430cb0da5b7982bd2287) that requires path-based suppressions.
   *
   * @see https://github.com/cdklabs/cdk-nag/blob/main/RULES.md
   */
  private applyNagSuppressions(stack: Stack, evaluationConfigResource: AwsCustomResource): void {
    NagSuppressions.addResourceSuppressions(
      this.executionRole,
      [{ id: 'AwsSolutions-IAM5', reason: 'Wildcard required for dynamic CloudWatch Logs and global Bedrock models.' }],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      evaluationConfigResource,
      [{ id: 'AwsSolutions-IAM5', reason: 'Wildcard required for bedrock-agentcore and CloudWatch on dynamic resources.' }],
      true,
    );

    const singletonId = `AWS${AwsCustomResource.PROVIDER_FUNCTION_UUID.replace(/-/g, '')}`;
    const existingPaths = new Set(stack.node.findAll().map((n) => `/${n.node.path}`));
    const serviceRolePath = `/${stack.stackName}/${singletonId}/ServiceRole/Resource`;
    const lambdaPath = `/${stack.stackName}/${singletonId}/Resource`;

    if (existingPaths.has(serviceRolePath)) {
      NagSuppressions.addResourceSuppressionsByPath(stack, serviceRolePath, [
        {
          id: 'AwsSolutions-IAM4',
          reason: 'AWS managed policy required by AwsCustomResource singleton Lambda.',
          appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'],
        },
      ]);
    }

    if (existingPaths.has(lambdaPath)) {
      NagSuppressions.addResourceSuppressionsByPath(stack, lambdaPath, [
        { id: 'AwsSolutions-L1', reason: 'Lambda runtime managed by CDK AwsCustomResource construct.' },
      ]);
    }
  }
}
