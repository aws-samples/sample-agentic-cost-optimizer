import { AgentRuntimeArtifact, Runtime } from '@aws-cdk/aws-bedrock-agentcore-alpha';
import { Stack } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { Platform } from 'aws-cdk-lib/aws-ecr-assets';
import { Effect, ManagedPolicy, Policy, PolicyDocument, PolicyStatement } from 'aws-cdk-lib/aws-iam';

import { InfraConfig } from '../constants/infra-config';

export interface AgentProps {
  agentRuntimeName: string;
  description?: string;
  dockerfilePath?: string;
  environmentVariables?: { [key: string]: string };
  buildArgs?: { [key: string]: string };
  platform?: Platform;
}

export class Agent extends Construct {
  public readonly runtime: Runtime;
  public readonly runtimeArn: string;

  constructor(scope: Construct, id: string, props: AgentProps) {
    super(scope, id);

    const {
      agentRuntimeName,
      description,
      dockerfilePath = 'Dockerfile',
      environmentVariables = {},
      buildArgs = {},
      platform = Platform.LINUX_ARM64,
    } = props;

    // Get environment from context (same as main stack)
    const environment = this.node.tryGetContext('env') || 'dev';

    // Get stack reference for pseudo parameters
    const stack = Stack.of(this);

    // Build Docker image from local asset
    const agentRuntimeArtifact = AgentRuntimeArtifact.fromAsset('../', {
      file: dockerfilePath,
      buildArgs: {
        ENVIRONMENT: environment,
        ...buildArgs,
      },
      platform,
    });

    // Create Agent Core runtime
    this.runtime = new Runtime(this, 'Runtime', {
      runtimeName: agentRuntimeName,
      agentRuntimeArtifact,
      description,
      environmentVariables: {
        ENVIRONMENT: environment,
        ...environmentVariables,
      },
    });

    // Attach AWS SecurityAudit managed policy for read-only access
    this.runtime.role.addManagedPolicy(ManagedPolicy.fromAwsManagedPolicyName('SecurityAudit'));

    // Create custome-managed policy for Bedrock model invocation
    const modelId = InfraConfig.inferenceProfileRegion
      ? `${InfraConfig.inferenceProfileRegion}.${InfraConfig.modelId}`
      : InfraConfig.modelId;

    const bedrockPolicy = new Policy(this, 'BedrockModelInvocationPolicy', {
      policyName: 'BedrockModelInvocation',
      document: new PolicyDocument({
        statements: [
          new PolicyStatement({
            sid: 'InvokeBedrockModel',
            effect: Effect.ALLOW,
            actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream'],
            resources: [
              `arn:${stack.partition}:bedrock:${stack.region}:${stack.account}:inference-profile/${modelId}`,
              `arn:${stack.partition}:bedrock:*::foundation-model/${InfraConfig.modelId}`,
            ],
          }),
        ],
      }),
    });
    bedrockPolicy.attachToRole(this.runtime.role);

    // Create custome-managed policy for monitoring
    const monitoringPolicy = new Policy(this, 'MonitoringPolicy', {
      policyName: 'MonitoringPolicy',
      document: new PolicyDocument({
        statements: [
          new PolicyStatement({
            sid: 'LambdaMonitoring',
            effect: Effect.ALLOW,
            actions: ['lambda:GetFunction', 'lambda:GetFunctionConcurrency', 'lambda:GetProvisionedConcurrencyConfig'],
            resources: ['*'],
          }),
          new PolicyStatement({
            sid: 'CloudWatchLogsMonitoring',
            effect: Effect.ALLOW,
            actions: [
              'cloudwatch:GetMetricStatistics',
              'logs:StartQuery',
              'logs:StopQuery',
              'logs:GetQueryResults',
              'logs:GetLogEvents',
              'logs:GetLogRecord',
              'logs:FilterLogEvents',
            ],
            resources: ['*'],
          }),
          new PolicyStatement({
            sid: 'PricingAccess',
            effect: Effect.ALLOW,
            actions: ['pricing:GetProducts'],
            resources: ['*'],
          }),
        ],
      }),
    });
    monitoringPolicy.attachToRole(this.runtime.role);

    this.runtimeArn = this.runtime.agentRuntimeArn;
  }
}
