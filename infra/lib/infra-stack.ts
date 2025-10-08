import { TypeScriptCode } from '@mrgrain/cdk-esbuild';
import { CfnOutput, CfnResource, Duration, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { DockerImageAsset, Platform } from 'aws-cdk-lib/aws-ecr-assets';
import { Effect, PolicyDocument, PolicyStatement, Role, ServicePrincipal } from 'aws-cdk-lib/aws-iam';
import { Function as LambdaFunction, Runtime } from 'aws-cdk-lib/aws-lambda';
import { Bucket, BucketEncryption } from 'aws-cdk-lib/aws-s3';

export class InfraStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Get environment from context
    const environment = this.node.tryGetContext('env') || 'dev';

    // Create S3 bucket for agent data storage
    const agentDataBucket = new Bucket(this, 'AgentDataBucket', {
      bucketName: `agent-data-${environment}-${this.account}-${this.region}`,
      removalPolicy: RemovalPolicy.DESTROY, // For development/POC
      versioned: true,
      encryption: BucketEncryption.S3_MANAGED,
      enforceSSL: true,
    });

    // Output the bucket name for use by other resources
    new CfnOutput(this, 'AgentDataBucketName', {
      value: agentDataBucket.bucketName,
      description: 'Name of the S3 bucket for agent data storage',
    });

    // Build and push Docker image to ECR automatically
    const agentDockerImage = new DockerImageAsset(this, 'AgentDockerImage', {
      directory: '../', // Build from project root where Dockerfile is located
      file: 'Dockerfile',
      buildArgs: {
        ENVIRONMENT: environment,
      },
      platform: Platform.LINUX_ARM64,
    });

    // Output the image URI with tag
    new CfnOutput(this, 'AgentImageUri', {
      value: agentDockerImage.imageUri,
      description: 'URI of the built Docker image in ECR',
    });

    // Create IAM role for Agent Core runtime (matching agentcore configure generated role)
    const agentCoreRole = new Role(this, 'AgentCoreRole', {
      assumedBy: new ServicePrincipal('bedrock-agentcore.amazonaws.com').withConditions({
        StringEquals: {
          'aws:SourceAccount': this.account,
        },
        ArnLike: {
          'aws:SourceArn': `arn:aws:bedrock-agentcore:${this.region}:${this.account}:*`,
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
              resources: [`arn:aws:ecr:${this.region}:${this.account}:repository/*`],
            }),
            new PolicyStatement({
              sid: 'ECRTokenAccess',
              effect: Effect.ALLOW,
              actions: ['ecr:GetAuthorizationToken'],
              resources: ['*'],
            }),
            // CloudWatch Logs permissions (split into multiple statements like working role)
            new PolicyStatement({
              effect: Effect.ALLOW,
              actions: ['logs:DescribeLogStreams', 'logs:CreateLogGroup'],
              resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*`],
            }),
            new PolicyStatement({
              effect: Effect.ALLOW,
              actions: ['logs:DescribeLogGroups'],
              resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`],
            }),
            new PolicyStatement({
              effect: Effect.ALLOW,
              actions: ['logs:CreateLogStream', 'logs:PutLogEvents'],
              resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`],
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
              resources: [`arn:aws:bedrock-agentcore:${this.region}:${this.account}:runtime/*`],
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
              resources: [`arn:aws:bedrock-agentcore:${this.region}:${this.account}:memory/*`],
            }),
            // BedrockAgentCore Identity permissions
            new PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetResourceApiKey',
              effect: Effect.ALLOW,
              actions: ['bedrock-agentcore:GetResourceApiKey'],
              resources: [
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default/apikeycredentialprovider/*`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/agent-*`,
              ],
            }),
            new PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetCredentialProviderClientSecret',
              effect: Effect.ALLOW,
              actions: ['secretsmanager:GetSecretValue'],
              resources: [`arn:aws:secretsmanager:${this.region}:${this.account}:secret:bedrock-agentcore-identity!default/oauth2/*`],
            }),
            new PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetResourceOauth2Token',
              effect: Effect.ALLOW,
              actions: ['bedrock-agentcore:GetResourceOauth2Token'],
              resources: [
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default/oauth2credentialprovider/*`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/agent-*`,
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
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/agent-*`,
              ],
            }),
            // Bedrock model invocation permissions (enhanced)
            new PolicyStatement({
              sid: 'BedrockModelInvocation',
              effect: Effect.ALLOW,
              actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream', 'bedrock:ApplyGuardrail'],
              resources: [
                'arn:aws:bedrock:*::foundation-model/*',
                'arn:aws:bedrock:*:*:inference-profile/*',
                `arn:aws:bedrock:${this.region}:${this.account}:*`,
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
                `arn:aws:bedrock-agentcore:${this.region}:aws:code-interpreter/*`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:code-interpreter/*`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:code-interpreter-custom/*`,
              ],
            }),
          ],
        }),
      },
    });

    // Grant S3 bucket access to the Agent Core role
    agentDataBucket.grantReadWrite(agentCoreRole);
    agentCoreRole.addToPolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['lambda:GetFunctionConfiguration', 'lambda:ListFunctions'],
        resources: ['*'], // TODO: tighten this down if possible
      }),
    );
    agentCoreRole.addToPolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: [
          'cloudwatch:StartQuery',
          'cloudwatch:StopQuery',
          'cloudwatch:GetQueryResults',
          'logs:DescribeLogGroups',
          'logs:DescribeLogStreams',
          'logs:GetLogEvents',
          'logs:GetLogRecord',
          'logs:FilterLogEvents',
        ],
        resources: ['*'], // TODO: tighten this down if possible
      }),
    );

    // Create Agent Core runtime using CfnResource
    const agentCoreRuntime = new CfnResource(this, 'AgentCoreRuntime', {
      type: 'AWS::BedrockAgentCore::Runtime',
      properties: {
        AgentRuntimeName: `agentRuntime${environment}`,
        RoleArn: agentCoreRole.roleArn,
        AgentRuntimeArtifact: {
          ContainerConfiguration: {
            ContainerUri: agentDockerImage.imageUri,
          },
        },
        NetworkConfiguration: {
          NetworkMode: 'PUBLIC',
        },
        EnvironmentVariables: {
          BYPASS_TOOL_CONSENT: 'true',
          S3_BUCKET_NAME: agentDataBucket.bucketName,
          ENVIRONMENT: environment,
        },
      },
    });

    // Output the runtime ARN for Lambda function reference
    new CfnOutput(this, 'AgentCoreRuntimeArn', {
      value: agentCoreRuntime.getAtt('AgentRuntimeArn').toString(),
      description: 'ARN of the Agent Core runtime',
    });

    // Create Lambda function for agent invocation
    const agentInvokerFunction = new LambdaFunction(this, 'AgentInvokerFunction', {
      functionName: `AgentInvokerFunction-${environment}`,
      runtime: Runtime.NODEJS_22_X,
      handler: 'agent-invoker.handler',
      code: new TypeScriptCode('lambda/agent-invoker.ts'),
      timeout: Duration.minutes(5),
      memorySize: 512,
      environment: {
        AGENT_CORE_RUNTIME_ARN: agentCoreRuntime.getAtt('AgentRuntimeArn').toString(),
        ENVIRONMENT: environment,
      },
      description: 'Lambda function to invoke Agent Core runtime',
    });

    // Grant Lambda permission to invoke Agent Core runtime
    agentInvokerFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['bedrock-agentcore:InvokeAgentRuntime', 'bedrock-agentcore:GetRuntime'],
        resources: [agentCoreRuntime.getAtt('AgentRuntimeArn').toString(), `${agentCoreRuntime.getAtt('AgentRuntimeArn').toString()}/*`],
      }),
    );

    // Grant Lambda permission to write logs
    agentInvokerFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
        resources: ['*'],
      }),
    );

    // Output the Lambda function ARN
    new CfnOutput(this, 'AgentInvokerFunctionArn', {
      value: agentInvokerFunction.functionArn,
      description: 'ARN of the Lambda function for agent invocation',
    });
  }
}
