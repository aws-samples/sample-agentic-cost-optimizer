import { CfnOutput, Fn, RemovalPolicy, Stack, type StackProps } from 'aws-cdk-lib';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

import { AttributeType, BillingMode, Table } from 'aws-cdk-lib/aws-dynamodb';
import { EventField, EventPattern, Rule, RuleTargetInput, Schedule } from 'aws-cdk-lib/aws-events';
import { SfnStateMachine } from 'aws-cdk-lib/aws-events-targets';
import { ArnPrincipal, Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Bucket, BucketEncryption } from 'aws-cdk-lib/aws-s3';

import { InfraConfig } from '../constants/infra-config';
import { Agent } from './agent';
import { Evals } from './evals';
import { Gateway } from './gateway';
import { Workflow } from './workflow';

export interface InfraStackProps extends StackProps {
  /**
   * Environment name
   */
  environment: string;
  /**
   * Version suffix for runtime naming (bump on breaking changes)
   */
  runtimeVersion: string;
  /**
   * Enable scheduled trigger rule
   */
  enableScheduledTrigger: boolean;
  /**
   * Enable manual trigger rule for testing
   */
  enableManualTrigger: boolean;
  /**
   * Enable Online Evaluations for the agent
   */
  enableEvals: boolean;
}

export class InfraStack extends Stack {
  public readonly agent: Agent;
  public readonly evals?: Evals;

  constructor(scope: Construct, id: string, props: InfraStackProps) {
    super(scope, id, props);

    const { environment, runtimeVersion, enableScheduledTrigger, enableManualTrigger, enableEvals } = props;

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
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true,
      },
    });

    const accessLogsBucket = new Bucket(this, 'AccessLogsBucket', {
      bucketName: `access-logs-${environment}-${this.account}-${this.region}`,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      encryption: BucketEncryption.S3_MANAGED,
      enforceSSL: true,
    });

    const agentDataBucket = new Bucket(this, 'AgentDataBucket', {
      bucketName: `agent-data-${environment}-${this.account}-${this.region}`,
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true, // For development/POC - remove for production to prevent data loss
      versioned: true,
      encryption: BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      serverAccessLogsBucket: accessLogsBucket,
      serverAccessLogsPrefix: 'agent-data-logs/',
    });

    const gateway = new Gateway(this, 'Gateway', {
      agentDataBucket,
      journalTableName: agentsTable.tableName,
      journalTableArn: agentsTable.tableArn,
      ttlDays: InfraConfig.ttlDays,
      environment,
    });

    NagSuppressions.addResourceSuppressionsByPath(
      this,
      `/${this.node.path}/AWS679f53fac002430cb0da5b7982bd2287`,
      [
        {
          id: 'AwsSolutions-IAM4',
          reason: 'CDK auto-generated custom resource Lambda for AgentCore Gateway L2 construct. Managed by CDK.',
          appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'],
        },
        {
          id: 'AwsSolutions-L1',
          reason: 'CDK auto-generated custom resource Lambda. Runtime managed by CDK.',
        },
      ],
      true,
    );

    this.agent = new Agent(this, 'AgentCore', {
      agentRuntimeName: `agentRuntime_${environment}_${runtimeVersion}`,
      description: `Agent runtime for ${environment} environment`,
      environment,
      modelId: InfraConfig.modelId,
      inferenceProfileRegion: InfraConfig.inferenceProfileRegion,
      environmentVariables: {
        BYPASS_TOOL_CONSENT: 'true',
        JOURNAL_TABLE_NAME: agentsTable.tableName,
        AWS_REGION: this.region,
        TTL_DAYS: InfraConfig.ttlDays.toString(),
        GATEWAY_MCP_URL: gateway.gatewayUrl,
        GATEWAY_TOKEN_ENDPOINT: gateway.tokenEndpoint,
        GATEWAY_CLIENT_ID: gateway.clientId,
        GATEWAY_CLIENT_SECRET: gateway.clientSecret.unsafeUnwrap(),
        GATEWAY_SCOPE: gateway.scope,
      },
    });

    const workflow = new Workflow(this, 'AgentWorkflow', {
      agentRuntimeArn: this.agent.runtimeArn,
      journalTable: agentsTable,
      environment,
      ttlDays: InfraConfig.ttlDays,
      lambdaLogLevel: InfraConfig.lambdaLogLevel,
    });

    agentsTable.addToResourcePolicy(
      new PolicyStatement({
        sid: 'AllowAgentRuntimePutItem',
        effect: Effect.ALLOW,
        principals: [new ArnPrincipal(this.agent.runtime.role.roleArn)],
        actions: ['dynamodb:PutItem'],
        resources: [Fn.sub('arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/agents-table-${environment}', { environment })],
      }),
    );

    agentsTable.addToResourcePolicy(
      new PolicyStatement({
        sid: 'AllowAgentInvokerPutItem',
        effect: Effect.ALLOW,
        principals: [new ArnPrincipal(workflow.agentInvokerFunction.role!.roleArn)],
        actions: ['dynamodb:PutItem'],
        resources: [Fn.sub('arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/agents-table-${environment}', { environment })],
      }),
    );

    agentsTable.addToResourcePolicy(
      new PolicyStatement({
        sid: 'AllowSessionInitializerPutItem',
        effect: Effect.ALLOW,
        principals: [new ArnPrincipal(workflow.sessionInitializerFunction.role!.roleArn)],
        actions: ['dynamodb:PutItem'],
        resources: [Fn.sub('arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/agents-table-${environment}', { environment })],
      }),
    );

    agentsTable.addToResourcePolicy(
      new PolicyStatement({
        sid: 'AllowStateMachineQuery',
        effect: Effect.ALLOW,
        principals: [new ArnPrincipal(workflow.stateMachine.role.roleArn)],
        actions: ['dynamodb:Query'],
        resources: [Fn.sub('arn:aws:dynamodb:${AWS::Region}:${AWS::AccountId}:table/agents-table-${environment}', { environment })],
      }),
    );

    // Scheduled trigger rule - only deployed when enabled (default: prod only)
    if (enableScheduledTrigger) {
      const scheduledTriggerRule = new Rule(this, 'ScheduledTriggerRule', {
        schedule: Schedule.cron({ hour: '6', minute: '0' }),
        description: 'Rule to trigger agent workflow daily at 6am UTC',
      });

      scheduledTriggerRule.addTarget(
        new SfnStateMachine(workflow.stateMachine, {
          input: RuleTargetInput.fromObject({
            // Use EventField.eventId (UUID format, 36 chars) to meet AgentCore's 33+ character requirement
            session_id: EventField.eventId,
          }),
        }),
      );

      new CfnOutput(this, 'ScheduledTriggerRuleArn', {
        value: scheduledTriggerRule.ruleArn,
        description: 'ARN of the EventBridge rule for scheduled workflow triggers (daily at 6am UTC)',
      });
    }

    // Manual trigger rule is only deployed for any environment but prod
    if (enableManualTrigger) {
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

      new CfnOutput(this, 'ManualTriggerRuleArn', {
        value: manualTriggerRule.ruleArn,
        description: 'ARN of the EventBridge rule for manual workflow triggers',
      });
    }

    // Online Evaluations - conditionally create when enableEvals is true (default: prod only)
    if (enableEvals) {
      this.evals = new Evals(this, 'OnlineEvals', {
        agent: this.agent,
        environment,
      });

      new CfnOutput(this, 'EvaluationConfigId', {
        value: this.evals.configId,
        description: 'ID of the AgentCore Online Evaluation configuration',
      });

      new CfnOutput(this, 'EvaluationConfigArn', {
        value: this.evals.configArn,
        description: 'ARN of the AgentCore Online Evaluation configuration',
      });
    }

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
      value: workflow.agentInvokerFunction.functionArn,
      description: 'ARN of the Lambda function for agent invocation',
    });

    new CfnOutput(this, 'WorkflowStateMachineArn', {
      value: workflow.stateMachine.stateMachineArn,
      description: 'ARN of the Step Function state machine for agent workflow',
    });

    new CfnOutput(this, 'GatewayUrl', {
      value: gateway.gatewayUrl,
      description: 'AgentCore Gateway MCP endpoint URL',
    });

    new CfnOutput(this, 'GatewayTokenEndpoint', {
      value: gateway.tokenEndpoint,
      description: 'Cognito OAuth2 token endpoint for gateway auth',
    });

    new CfnOutput(this, 'GatewayClientId', {
      value: gateway.clientId,
      description: 'Cognito client ID for gateway auth',
    });
  }
}
