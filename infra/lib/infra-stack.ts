import { TypeScriptCode } from '@mrgrain/cdk-esbuild';
import { CfnOutput, Duration, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { AttributeType, Table } from 'aws-cdk-lib/aws-dynamodb';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Function as LambdaFunction, Runtime } from 'aws-cdk-lib/aws-lambda';
import { Bucket, BucketEncryption } from 'aws-cdk-lib/aws-s3';

import { Agent } from './agent';

export class InfraStack extends Stack {
  public readonly agent: Agent;

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Get environment from context
    const environment = this.node.tryGetContext('env') || 'dev';

    // Create DynamoDB table for agents
    const agentsTable = new Table(this, 'AgentsTable', {
      tableName: `agents-table-${environment}`,
      partitionKey: {
        name: 'PK',
        type: AttributeType.STRING,
      },
      sortKey: {
        name: 'SK',
        type: AttributeType.STRING,
      },
      removalPolicy: RemovalPolicy.DESTROY, // For development/POC
    });

    // Output the table name
    new CfnOutput(this, 'AgentsTableName', {
      value: agentsTable.tableName,
      description: 'Name of the DynamoDB table for agents',
    });

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

    // Create agent using the Agent class
    this.agent = new Agent(this, 'AgentCore', {
      agentRuntimeName: `agentRuntime${environment}`,
      description: `Agent runtime for ${environment} environment`,
      dockerfilePath: 'Dockerfile',
      environmentVariables: {
        S3_BUCKET_NAME: agentDataBucket.bucketName,
      },
    });

    // Grant S3 bucket access to the agent role
    agentDataBucket.grantReadWrite(this.agent.role);

    // Add S3 agent-specific permissions for cost optimization analysis
    this.agent.role.addToPolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['lambda:GetFunctionConfiguration', 'lambda:ListFunctions'],
        resources: ['*'],
      }),
    );

    this.agent.role.addToPolicy(
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

    // Output the image URI with tag
    new CfnOutput(this, 'AgentImageUri', {
      value: this.agent.dockerImage.imageUri,
      description: 'URI of the built agent Docker image in ECR',
    });

    // Output the runtime ARN for Lambda function reference
    new CfnOutput(this, 'AgentCoreRuntimeArn', {
      value: this.agent.runtimeArn,
      description: 'ARN of the Agent Core runtime',
    });

    // Create Lambda function for agent invocation
    const agentInvokerFunction = new LambdaFunction(this, 'AgentInvokerFunction', {
      runtime: Runtime.NODEJS_22_X,
      handler: 'agent-invoker.handler',
      code: new TypeScriptCode('lambda/agent-invoker.ts'),
      timeout: Duration.minutes(5),
      memorySize: 512,
      environment: {
        AGENT_CORE_RUNTIME_ARN: this.agent.runtimeArn,
        ENVIRONMENT: environment,
      },
      description: 'Lambda function to invoke Agent Core runtime',
    });

    // Grant Lambda permission to invoke Agent Core runtime
    agentInvokerFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['bedrock-agentcore:InvokeAgentRuntime', 'bedrock-agentcore:GetRuntime'],
        resources: [this.agent.runtimeArn, `${this.agent.runtimeArn}/*`],
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
