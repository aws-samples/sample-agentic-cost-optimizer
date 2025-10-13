import { CfnResource, Stack } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { DockerImageAsset, Platform } from 'aws-cdk-lib/aws-ecr-assets';
import { Effect, PolicyDocument, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';

export interface AgentProps {
  agentRuntimeName: string;
  description?: string;
  dockerfilePath?: string;
  environmentVariables?: { [key: string]: string };
  buildArgs?: { [key: string]: string };
  platform?: Platform;
}

export class Agent extends Construct {
  public readonly role: Role;
  public readonly runtimeArn: string;
  public readonly dockerImage: DockerImageAsset;
  public readonly runtime: CfnResource;

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

    // Get stack reference for account and region
    const stack = Stack.of(this);

    // Build and push Docker image to ECR automatically
    this.dockerImage = new DockerImageAsset(this, 'DockerImage', {
      directory: '../', // Build from project root
      file: dockerfilePath,
      buildArgs: {
        ENVIRONMENT: environment,
        ...buildArgs,
      },
      platform,
    });

    // Create IAM role for Agent Core runtime
    this.role = new Role(this, 'Role', {
      assumedBy: new ServicePrincipal('bedrock-agentcore.amazonaws.com').withConditions({
        StringEquals: {
          'aws:SourceAccount': stack.account,
        },
        ArnLike: {
          'aws:SourceArn': `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:*`,
        },
      }),
      description: 'IAM role for Agent Core runtime execution',
      inlinePolicies: {
        AgentCoreExecutionPolicy: new PolicyDocument({
          statements: [
            // ECR permissions for container image access
            new PolicyStatement({
              sid: 'ECRImageAccess',
              effect: Effect.ALLOW,
              actions: ['ecr:BatchGetImage', 'ecr:GetDownloadUrlForLayer'],
              resources: [`arn:aws:ecr:${stack.region}:${stack.account}:repository/*`],
            }),
            new PolicyStatement({
              sid: 'ECRTokenAccess',
              effect: Effect.ALLOW,
              actions: ['ecr:GetAuthorizationToken'],
              resources: ['*'],
            }),
            // CloudWatch Logs permissions
            new PolicyStatement({
              effect: Effect.ALLOW,
              actions: ['logs:DescribeLogStreams', 'logs:CreateLogGroup'],
              resources: [`arn:aws:logs:${stack.region}:${stack.account}:log-group:/aws/bedrock-agentcore/runtimes/*`],
            }),
            new PolicyStatement({
              effect: Effect.ALLOW,
              actions: ['logs:DescribeLogGroups'],
              resources: [`arn:aws:logs:${stack.region}:${stack.account}:log-group:*`],
            }),
            new PolicyStatement({
              effect: Effect.ALLOW,
              actions: ['logs:CreateLogStream', 'logs:PutLogEvents'],
              resources: [`arn:aws:logs:${stack.region}:${stack.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`],
            }),
            // X-Ray tracing permissions
            new PolicyStatement({
              effect: Effect.ALLOW,
              actions: ['xray:PutTraceSegments', 'xray:PutTelemetryRecords', 'xray:GetSamplingRules', 'xray:GetSamplingTargets'],
              resources: ['*'],
            }),
            // CloudWatch metrics permissions
            new PolicyStatement({
              effect: Effect.ALLOW,
              actions: ['cloudwatch:PutMetricData'],
              resources: ['*'],
              conditions: {
                StringEquals: {
                  'cloudwatch:namespace': 'bedrock-agentcore',
                },
              },
            }),
            // BedrockAgentCore Runtime permissions
            new PolicyStatement({
              sid: 'BedrockAgentCoreRuntime',
              effect: Effect.ALLOW,
              actions: ['bedrock-agentcore:InvokeAgentRuntime'],
              resources: [`arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:runtime/*`],
            }),
            // BedrockAgentCore Memory permissions
            new PolicyStatement({
              sid: 'BedrockAgentCoreMemoryCreateMemory',
              effect: Effect.ALLOW,
              actions: ['bedrock-agentcore:CreateMemory'],
              resources: ['*'],
            }),
            new PolicyStatement({
              sid: 'BedrockAgentCoreMemory',
              effect: Effect.ALLOW,
              actions: [
                'bedrock-agentcore:CreateEvent',
                'bedrock-agentcore:GetEvent',
                'bedrock-agentcore:GetMemory',
                'bedrock-agentcore:GetMemoryRecord',
                'bedrock-agentcore:ListActors',
                'bedrock-agentcore:ListEvents',
                'bedrock-agentcore:ListMemoryRecords',
                'bedrock-agentcore:ListSessions',
                'bedrock-agentcore:DeleteEvent',
                'bedrock-agentcore:DeleteMemoryRecord',
                'bedrock-agentcore:RetrieveMemoryRecords',
              ],
              resources: [`arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:memory/*`],
            }),
            // BedrockAgentCore Identity permissions
            new PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetResourceApiKey',
              effect: Effect.ALLOW,
              actions: ['bedrock-agentcore:GetResourceApiKey'],
              resources: [
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:token-vault/default`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:token-vault/default/apikeycredentialprovider/*`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:workload-identity-directory/default/workload-identity/agent-*`,
              ],
            }),
            new PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetCredentialProviderClientSecret',
              effect: Effect.ALLOW,
              actions: ['secretsmanager:GetSecretValue'],
              resources: [`arn:aws:secretsmanager:${stack.region}:${stack.account}:secret:bedrock-agentcore-identity!default/oauth2/*`],
            }),
            new PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetResourceOauth2Token',
              effect: Effect.ALLOW,
              actions: ['bedrock-agentcore:GetResourceOauth2Token'],
              resources: [
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:token-vault/default`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:token-vault/default/oauth2credentialprovider/*`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:workload-identity-directory/default/workload-identity/agent-*`,
              ],
            }),
            new PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetWorkloadAccessToken',
              effect: Effect.ALLOW,
              actions: [
                'bedrock-agentcore:GetWorkloadAccessToken',
                'bedrock-agentcore:GetWorkloadAccessTokenForJWT',
                'bedrock-agentcore:GetWorkloadAccessTokenForUserId',
              ],
              resources: [
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:workload-identity-directory/default/workload-identity/agent-*`,
              ],
            }),
            // Bedrock model invocation permissions
            new PolicyStatement({
              sid: 'BedrockModelInvocation',
              effect: Effect.ALLOW,
              actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream', 'bedrock:ApplyGuardrail'],
              resources: [
                'arn:aws:bedrock:*::foundation-model/*',
                'arn:aws:bedrock:*:*:inference-profile/*',
                `arn:aws:bedrock:${stack.region}:${stack.account}:*`,
              ],
            }),
            // BedrockAgentCore Code Interpreter permissions
            new PolicyStatement({
              sid: 'BedrockAgentCoreCodeInterpreter',
              effect: Effect.ALLOW,
              actions: [
                'bedrock-agentcore:CreateCodeInterpreter',
                'bedrock-agentcore:StartCodeInterpreterSession',
                'bedrock-agentcore:InvokeCodeInterpreter',
                'bedrock-agentcore:StopCodeInterpreterSession',
                'bedrock-agentcore:DeleteCodeInterpreter',
                'bedrock-agentcore:ListCodeInterpreters',
                'bedrock-agentcore:GetCodeInterpreter',
                'bedrock-agentcore:GetCodeInterpreterSession',
                'bedrock-agentcore:ListCodeInterpreterSessions',
              ],
              resources: [
                `arn:aws:bedrock-agentcore:${stack.region}:aws:code-interpreter/*`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:code-interpreter/*`,
                `arn:aws:bedrock-agentcore:${stack.region}:${stack.account}:code-interpreter-custom/*`,
              ],
            }),
          ],
        }),
      },
    });

    // Create Agent Core runtime using CfnResource
    this.runtime = new CfnResource(this, 'Runtime', {
      type: 'AWS::BedrockAgentCore::Runtime',
      properties: {
        AgentRuntimeName: agentRuntimeName,
        RoleArn: this.role.roleArn,
        AgentRuntimeArtifact: {
          ContainerConfiguration: {
            ContainerUri: this.dockerImage.imageUri,
          },
        },
        NetworkConfiguration: {
          NetworkMode: 'PUBLIC',
        },
        EnvironmentVariables: {
          BYPASS_TOOL_CONSENT: 'true',
          ENVIRONMENT: environment,
          ...environmentVariables,
        },
        ...(description && { Description: description }),
      },
    });

    // Store the runtime ARN for easy access
    this.runtimeArn = this.runtime.getAtt('AgentRuntimeArn').toString();
  }
}
