import { AgentCoreRuntime, AgentRuntimeArtifact, Runtime } from '@aws-cdk/aws-bedrock-agentcore-alpha';
import { Stack } from 'aws-cdk-lib';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

import { Effect, Policy, PolicyDocument, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Asset } from 'aws-cdk-lib/aws-s3-assets';

import { InfraConfig } from '../constants/infra-config';

export interface AgentProps {
  agentRuntimeName: string;
  description?: string;
  environmentVariables?: { [key: string]: string };
}

export class Agent extends Construct {
  public readonly runtime: Runtime;
  public readonly runtimeArn: string;

  constructor(scope: Construct, id: string, props: AgentProps) {
    super(scope, id);

    const { agentRuntimeName, description, environmentVariables = {} } = props;

    const environment = this.node.tryGetContext('env') || 'dev';
    const stack = Stack.of(this);

    // Reference pre-built AgentCore Runtime package (built by build-deployment-package script)
    const deploymentPackage = new Asset(this, 'AgentCoreRuntimePackage', {
      path: './dist/agentcore_runtime.zip',
    });

    // Use agent-as-code deployment from S3 with OTEL instrumentation
    const agentRuntimeArtifact = AgentRuntimeArtifact.fromS3(
      {
        bucketName: deploymentPackage.s3BucketName,
        objectKey: deploymentPackage.s3ObjectKey,
      },
      AgentCoreRuntime.PYTHON_3_12,
      ['opentelemetry-instrument', 'src/agents/main.py'],
    );

    this.runtime = new Runtime(this, 'Runtime', {
      runtimeName: agentRuntimeName,
      agentRuntimeArtifact,
      description,
      environmentVariables: {
        ENVIRONMENT: environment,
        ...environmentVariables,
      },
    });

    deploymentPackage.grantRead(this.runtime.role);

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

    const monitoringPolicy = new Policy(this, 'MonitoringPolicy', {
      policyName: 'MonitoringPolicy',
      document: new PolicyDocument({
        statements: [
          new PolicyStatement({
            sid: 'LambdaMonitoring',
            effect: Effect.ALLOW,
            actions: [
              'lambda:GetFunction',
              'lambda:GetFunctionConfiguration',
              'lambda:GetFunctionConcurrency',
              'lambda:GetProvisionedConcurrencyConfig',
              'lambda:ListProvisionedConcurrencyConfigs',
              'lambda:ListFunctions',
            ],
            resources: ['*'],
          }),
          new PolicyStatement({
            sid: 'CloudWatchMetricsAccess',
            effect: Effect.ALLOW,
            actions: ['cloudwatch:GetMetricStatistics', 'cloudwatch:ListMetrics'],
            resources: ['*'],
          }),
          new PolicyStatement({
            sid: 'CloudWatchLogsQueryAccess',
            effect: Effect.ALLOW,
            actions: ['logs:StopQuery', 'logs:GetQueryResults'],
            resources: ['*'],
          }),
          new PolicyStatement({
            sid: 'CloudWatchLogsAccess',
            effect: Effect.ALLOW,
            actions: ['logs:StartQuery', 'logs:GetLogEvents', 'logs:GetLogRecord', 'logs:FilterLogEvents'],
            // Scoped to Lambda log groups to control which CloudWatch Logs the agent can access.
            // Modify the resource pattern below (e.g., restrict to specific function names or log group patterns)
            resources: [`arn:${stack.partition}:logs:*:*:log-group:/aws/lambda/*`],
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

    this.applyNagSuppressions(bedrockPolicy, monitoringPolicy);
  }

  private applyNagSuppressions(bedrockPolicy: Policy, monitoringPolicy: Policy): void {
    NagSuppressions.addResourceSuppressions(
      this.runtime,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Wildcard permissions required by AgentCore Runtime construct for CloudWatch Logs, S3 operations, and workload identity management. Auto-generated by @aws-cdk/aws-bedrock-agentcore-alpha.',
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      bedrockPolicy,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Region wildcard required for Bedrock foundation model access. Foundation models are global resources accessible from any region. Model ID is specifically scoped.',
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      monitoringPolicy,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Wildcard resources required for read-only monitoring operations. Lambda functions and CloudWatch resources are created dynamically. Pricing API does not support resource-level permissions. All actions are read-only.',
        },
      ],
      true,
    );
  }
}
