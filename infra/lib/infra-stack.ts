import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import * as ecr_assets from 'aws-cdk-lib/aws-ecr-assets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';

export class InfraStack extends cdk.Stack {
  public readonly agentDataBucket: s3.Bucket;

  public readonly agentDockerImage: ecr_assets.DockerImageAsset;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Get environment from context
    const environment = this.node.tryGetContext('env') || 'dev';

    // Create S3 bucket for agent data storage
    this.agentDataBucket = new s3.Bucket(this, 'AgentDataBucket', {
      bucketName: `agent-data-${environment}-${this.account}-${this.region}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // For development/POC
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
    });

    // Output the bucket name for use by other resources
    new cdk.CfnOutput(this, 'AgentDataBucketName', {
      value: this.agentDataBucket.bucketName,
      description: 'Name of the S3 bucket for agent data storage',
    });

    // Build and push Docker image to ECR automatically
    this.agentDockerImage = new ecr_assets.DockerImageAsset(this, 'AgentDockerImage', {
      directory: '../', // Build from project root where Dockerfile is located
      file: 'Dockerfile',
      buildArgs: {
        ENVIRONMENT: environment,
      },
      platform: ecr_assets.Platform.LINUX_ARM64,
    });

    // Output the image URI with tag
    new cdk.CfnOutput(this, 'AgentImageUri', {
      value: this.agentDockerImage.imageUri,
      description: 'URI of the built Docker image in ECR',
    });

    // Create IAM role for Agent Core runtime (matching agentcore configure generated role)
    const agentCoreRole = new iam.Role(this, 'AgentCoreRole', {
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com').withConditions({
        StringEquals: {
          'aws:SourceAccount': this.account,
        },
        ArnLike: {
          'aws:SourceArn': `arn:aws:bedrock-agentcore:${this.region}:${this.account}:*`,
        },
      }),
      description: 'IAM role for Agent Core runtime execution',
      inlinePolicies: {
        AgentCoreExecutionPolicy: new iam.PolicyDocument({
          statements: [
            // ECR permissions for container image access
            new iam.PolicyStatement({
              sid: 'ECRImageAccess',
              effect: iam.Effect.ALLOW,
              actions: ['ecr:BatchGetImage', 'ecr:GetDownloadUrlForLayer'],
              resources: [`arn:aws:ecr:${this.region}:${this.account}:repository/*`],
            }),
            new iam.PolicyStatement({
              sid: 'ECRTokenAccess',
              effect: iam.Effect.ALLOW,
              actions: ['ecr:GetAuthorizationToken'],
              resources: ['*'],
            }),
            // CloudWatch Logs permissions (split into multiple statements like working role)
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['logs:DescribeLogStreams', 'logs:CreateLogGroup'],
              resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*`],
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['logs:DescribeLogGroups'],
              resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:*`],
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['logs:CreateLogStream', 'logs:PutLogEvents'],
              resources: [`arn:aws:logs:${this.region}:${this.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*`],
            }),
            // X-Ray tracing permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['xray:PutTraceSegments', 'xray:PutTelemetryRecords', 'xray:GetSamplingRules', 'xray:GetSamplingTargets'],
              resources: ['*'],
            }),
            // CloudWatch metrics permissions
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['cloudwatch:PutMetricData'],
              resources: ['*'],
              conditions: {
                StringEquals: {
                  'cloudwatch:namespace': 'bedrock-agentcore',
                },
              },
            }),
            // BedrockAgentCore Runtime permissions
            new iam.PolicyStatement({
              sid: 'BedrockAgentCoreRuntime',
              effect: iam.Effect.ALLOW,
              actions: ['bedrock-agentcore:InvokeAgentRuntime'],
              resources: [`arn:aws:bedrock-agentcore:${this.region}:${this.account}:runtime/*`],
            }),
            // BedrockAgentCore Memory permissions
            new iam.PolicyStatement({
              sid: 'BedrockAgentCoreMemoryCreateMemory',
              effect: iam.Effect.ALLOW,
              actions: ['bedrock-agentcore:CreateMemory'],
              resources: ['*'],
            }),
            new iam.PolicyStatement({
              sid: 'BedrockAgentCoreMemory',
              effect: iam.Effect.ALLOW,
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
            new iam.PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetResourceApiKey',
              effect: iam.Effect.ALLOW,
              actions: ['bedrock-agentcore:GetResourceApiKey'],
              resources: [
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default/apikeycredentialprovider/*`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/agent-*`,
              ],
            }),
            new iam.PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetCredentialProviderClientSecret',
              effect: iam.Effect.ALLOW,
              actions: ['secretsmanager:GetSecretValue'],
              resources: [`arn:aws:secretsmanager:${this.region}:${this.account}:secret:bedrock-agentcore-identity!default/oauth2/*`],
            }),
            new iam.PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetResourceOauth2Token',
              effect: iam.Effect.ALLOW,
              actions: ['bedrock-agentcore:GetResourceOauth2Token'],
              resources: [
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:token-vault/default/oauth2credentialprovider/*`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default`,
                `arn:aws:bedrock-agentcore:${this.region}:${this.account}:workload-identity-directory/default/workload-identity/agent-*`,
              ],
            }),
            new iam.PolicyStatement({
              sid: 'BedrockAgentCoreIdentityGetWorkloadAccessToken',
              effect: iam.Effect.ALLOW,
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
            new iam.PolicyStatement({
              sid: 'BedrockModelInvocation',
              effect: iam.Effect.ALLOW,
              actions: ['bedrock:InvokeModel', 'bedrock:InvokeModelWithResponseStream', 'bedrock:ApplyGuardrail'],
              resources: [
                'arn:aws:bedrock:*::foundation-model/*',
                'arn:aws:bedrock:*:*:inference-profile/*',
                `arn:aws:bedrock:${this.region}:${this.account}:*`,
              ],
            }),
            // BedrockAgentCore Code Interpreter permissions
            new iam.PolicyStatement({
              sid: 'BedrockAgentCoreCodeInterpreter',
              effect: iam.Effect.ALLOW,
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
    this.agentDataBucket.grantReadWrite(agentCoreRole);

    // Create Agent Core runtime using CfnResource
    const agentCoreRuntime = new cdk.CfnResource(this, 'AgentCoreRuntime', {
      type: 'AWS::BedrockAgentCore::Runtime',
      properties: {
        AgentRuntimeName: `agentRuntime${environment}`,
        RoleArn: agentCoreRole.roleArn,
        AgentRuntimeArtifact: {
          ContainerConfiguration: {
            ContainerUri: this.agentDockerImage.imageUri,
          },
        },
        NetworkConfiguration: {
          NetworkMode: 'PUBLIC',
        },
        EnvironmentVariables: {
          S3_BUCKET_NAME: this.agentDataBucket.bucketName,
          ENVIRONMENT: environment,
        },
      },
    });

    // Output the runtime ARN for Lambda function reference
    new cdk.CfnOutput(this, 'AgentCoreRuntimeArn', {
      value: agentCoreRuntime.getAtt('AgentRuntimeArn').toString(),
      description: 'ARN of the Agent Core runtime',
    });

    // Create Lambda function for agent invocation
    const agentInvokerFunction = new lambda.Function(this, 'AgentInvokerFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'agent-invoker.lambda_handler',
      code: lambda.Code.fromAsset('lambda'),
      timeout: cdk.Duration.minutes(5),
      memorySize: 512,
      environment: {
        AGENT_CORE_RUNTIME_ARN: agentCoreRuntime.getAtt('AgentRuntimeArn').toString(),
        S3_BUCKET_NAME: this.agentDataBucket.bucketName,
        ENVIRONMENT: environment,
      },
      description: 'Lambda function to invoke Agent Core runtime',
    });

    // Grant Lambda permission to invoke Agent Core runtime
    agentInvokerFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['bedrock-agentcore:InvokeAgentRuntime', 'bedrock-agentcore:GetRuntime'],
        resources: [agentCoreRuntime.getAtt('AgentRuntimeArn').toString(), `${agentCoreRuntime.getAtt('AgentRuntimeArn').toString()}/*`],
      }),
    );

    // Grant Lambda permission to write logs
    agentInvokerFunction.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
        resources: ['*'],
      }),
    );

    // Output the Lambda function ARN
    new cdk.CfnOutput(this, 'AgentInvokerFunctionArn', {
      value: agentInvokerFunction.functionArn,
      description: 'ARN of the Lambda function for agent invocation',
    });
  }
}
