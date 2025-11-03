import { TypeScriptCode } from '@mrgrain/cdk-esbuild';
import { CfnOutput, Duration, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { AttributeType, BillingMode, Table } from 'aws-cdk-lib/aws-dynamodb';
import { EventField, EventPattern, Rule, RuleTargetInput } from 'aws-cdk-lib/aws-events';
import { SfnStateMachine } from 'aws-cdk-lib/aws-events-targets';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Function as LambdaFunction, Runtime } from 'aws-cdk-lib/aws-lambda';
import { Bucket, BucketEncryption } from 'aws-cdk-lib/aws-s3';

import { Agent } from './agent';
import { Workflow } from './workflow';

export class InfraStack extends Stack {
  public readonly agent: Agent;

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Get environment and version from environment variables or context
    const environment = process.env.ENVIRONMENT || this.node.tryGetContext('env') || 'dev';
    const version = process.env.VERSION || this.node.tryGetContext('version') || 'v1';

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
      billingMode: BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY, // For development/POC
    });

    // Create S3 bucket for agent data storage
    const agentDataBucket = new Bucket(this, 'AgentDataBucket', {
      bucketName: `agent-data-${environment}-${this.account}-${this.region}`,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true, // Automatically empty bucket on stack deletion
      versioned: true,
      encryption: BucketEncryption.S3_MANAGED,
      enforceSSL: true,
    });

    // Create agent using the Agent class
    this.agent = new Agent(this, 'AgentCore', {
      agentRuntimeName: `agentRuntime_${environment}_${version}`,
      description: `Agent runtime for ${environment} environment`,
      dockerfilePath: 'Dockerfile',
      environmentVariables: {
        S3_BUCKET_NAME: agentDataBucket.bucketName,
        JOURNAL_TABLE_NAME: agentsTable.tableName,
        AWS_REGION: this.region,
      },
    });

    // Grant S3 bucket access to the agent role
    agentDataBucket.grantReadWrite(this.agent.runtime.role);

    // Grant DynamoDB table access to the agent role
    agentsTable.grantReadWriteData(this.agent.runtime.role);

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

    // Create Step Function workflow
    const workflow = new Workflow(this, 'AgentWorkflow', {
      agentInvokerFunction,
      journalTable: agentsTable,
    });

    // Create EventBridge rule for manual triggers
    const manualTriggerRule = new Rule(this, 'ManualTriggerRule', {
      eventPattern: {
        source: ['manual-trigger'],
        detailType: ['execute-agent'],
      } as EventPattern,
      description: 'Rule to trigger agent workflow via manual EventBridge events',
    });

    // Add Step Function as target
    manualTriggerRule.addTarget(
      new SfnStateMachine(workflow.stateMachine, {
        input: RuleTargetInput.fromObject({
          session_id: EventField.fromPath('$.id'),
        }),
      }),
    );

    // CloudFormation Outputs
    new CfnOutput(this, 'AgentsTableName', {
      value: agentsTable.tableName,
      description: 'Name of the DynamoDB table for agents',
    });

    new CfnOutput(this, 'AgentDataBucketName', {
      value: agentDataBucket.bucketName,
      description: 'Name of the S3 bucket for agent data storage',
    });

    new CfnOutput(this, 'AgentCoreRuntimeArn', {
      value: this.agent.runtimeArn,
      description: 'ARN of the Agent Core runtime',
    });

    new CfnOutput(this, 'AgentInvokerFunctionArn', {
      value: agentInvokerFunction.functionArn,
      description: 'ARN of the Lambda function for agent invocation',
    });

    new CfnOutput(this, 'WorkflowStateMachineArn', {
      value: workflow.stateMachine.stateMachineArn,
      description: 'ARN of the Step Function state machine for agent workflow',
    });

    new CfnOutput(this, 'ManualTriggerRuleArn', {
      value: manualTriggerRule.ruleArn,
      description: 'ARN of the EventBridge rule for manual workflow triggers',
    });
  }
}
