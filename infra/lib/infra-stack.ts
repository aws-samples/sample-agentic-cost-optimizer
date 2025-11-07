import { CfnOutput, Duration, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { AttributeType, BillingMode, Table } from 'aws-cdk-lib/aws-dynamodb';
import { EventField, EventPattern, Rule, RuleTargetInput } from 'aws-cdk-lib/aws-events';
import { SfnStateMachine } from 'aws-cdk-lib/aws-events-targets';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Code, Function, LayerVersion, Runtime, Tracing } from 'aws-cdk-lib/aws-lambda';
import { Bucket, BucketEncryption } from 'aws-cdk-lib/aws-s3';

import { InfraConfig } from '../constants/infra-config';
import { Agent } from './agent';
import { Workflow } from './workflow';

export class InfraStack extends Stack {
  public readonly agent: Agent;

  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const environment = process.env.ENVIRONMENT || this.node.tryGetContext('env') || 'dev';
    const version = process.env.VERSION || this.node.tryGetContext('version') || 'v1';

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
      removalPolicy: RemovalPolicy.DESTROY, // For development/POC - change to RETAIN for production
      timeToLiveAttribute: 'ttlSeconds',
    });

    const agentDataBucket = new Bucket(this, 'AgentDataBucket', {
      bucketName: `agent-data-${environment}-${this.account}-${this.region}`,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true, // For development/POC - remove for production to prevent data loss
      versioned: true,
      encryption: BucketEncryption.S3_MANAGED,
      enforceSSL: true,
    });

    const modelId = InfraConfig.inferenceProfileRegion
      ? `${InfraConfig.inferenceProfileRegion}.${InfraConfig.modelId}`
      : InfraConfig.modelId;

    this.agent = new Agent(this, 'AgentCore', {
      agentRuntimeName: `agentRuntime_${environment}_${version}`,
      description: `Agent runtime for ${environment} environment`,
      dockerfilePath: 'Dockerfile',
      environmentVariables: {
        BYPASS_TOOL_CONSENT: 'true',
        S3_BUCKET_NAME: agentDataBucket.bucketName,
        JOURNAL_TABLE_NAME: agentsTable.tableName,
        AWS_REGION: this.region,
        MODEL_ID: modelId,
        TTL_DAYS: InfraConfig.ttlDays.toString(),
      },
    });

    agentDataBucket.grantReadWrite(this.agent.runtime.role);
    agentsTable.grantReadWriteData(this.agent.runtime.role);

    const agentInvokerFunction = new Function(this, 'AgentInvoker', {
      runtime: Runtime.PYTHON_3_12,
      handler: 'agent_invoker.handler',
      code: Code.fromAsset('..', {
        bundling: {
          // Custom bundling: combines handler from infra/lambda with shared code from src/
          image: Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash',
            '-c',
            'cp infra/lambda/agent_invoker.py /asset-output/ && ' +
              'mkdir -p /asset-output/src && ' +
              'rsync -av --exclude="__pycache__" --exclude="*.pyc" src/shared src/__init__.py /asset-output/src/',
          ],
        },
        exclude: [
          'node_modules/**',
          '.venv/**',
          '.git/**',
          'infra/cdk.out/**',
          'infra/dist/**',
          'infra/node_modules/**',
          'infra/package-lock.json',
          '.pytest_cache/**',
          '.ruff_cache/**',
          '**/__pycache__/**',
          '**/*.pyc',
          'tests/**',
          '.kiro/**',
          '*.md',
          '.gitlab-ci.yml',
          'Makefile',
          'uv.lock',
        ],
      }),
      layers: [
        LayerVersion.fromLayerVersionArn(
          this,
          'PowertoolsLayer',
          `arn:aws:lambda:${this.region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:18`,
        ),
      ],
      timeout: Duration.minutes(5),
      memorySize: 512,
      tracing: Tracing.ACTIVE,
      environment: {
        AGENT_CORE_RUNTIME_ARN: this.agent.runtimeArn,
        JOURNAL_TABLE_NAME: agentsTable.tableName,
        TTL_DAYS: InfraConfig.ttlDays.toString(),
        ENVIRONMENT: environment,
        POWERTOOLS_SERVICE_NAME: InfraConfig.serviceName,
        LOG_LEVEL: InfraConfig.logLevel,
      },
      description: 'Lambda function to invoke Agent Core runtime',
    });

    agentInvokerFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['bedrock-agentcore:InvokeAgentRuntime', 'bedrock-agentcore:GetRuntime'],
        resources: [this.agent.runtimeArn, `${this.agent.runtimeArn}/*`],
      }),
    );

    agentInvokerFunction.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
        resources: ['*'],
      }),
    );

    agentsTable.grantWriteData(agentInvokerFunction);

    const workflow = new Workflow(this, 'AgentWorkflow', {
      agentInvokerFunction,
      journalTable: agentsTable,
      environment,
      ttlDays: InfraConfig.ttlDays,
      logLevel: InfraConfig.logLevel,
    });

    const manualTriggerRule = new Rule(this, 'ManualTriggerRule', {
      eventPattern: {
        source: ['manual-trigger'],
        detailType: ['execute-agent'],
      } as EventPattern,
      description: 'Rule to trigger agent workflow via manual EventBridge events',
    });

    manualTriggerRule.addTarget(
      new SfnStateMachine(workflow.stateMachine, {
        input: RuleTargetInput.fromObject({
          session_id: EventField.fromPath('$.id'),
        }),
      }),
    );

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

    new CfnOutput(this, 'SessionInitializerFunctionArn', {
      value: workflow.sessionInitializerFunction.functionArn,
      description: 'ARN of the Lambda function for session initialization',
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
