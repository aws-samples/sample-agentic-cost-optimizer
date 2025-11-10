import { Duration, Stack } from 'aws-cdk-lib';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

import { Table } from 'aws-cdk-lib/aws-dynamodb';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Code, Function, LayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { LogGroup, RetentionDays } from 'aws-cdk-lib/aws-logs';
import { Choice, Condition, DefinitionBody, Fail, JsonPath, StateMachine, Succeed, Wait, WaitTime } from 'aws-cdk-lib/aws-stepfunctions';
import { CallAwsService, LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';

import { EventStatus } from '../constants/event-statuses';
import { InfraConfig } from '../constants/infra-config';

export interface WorkflowProps {
  /**
   * The Lambda function that invokes the agent
   */
  agentInvokerFunction: Function;

  /**
   * The DynamoDB table for session journaling
   */
  journalTable: Table;

  /**
   * Environment name for resource naming
   */
  environment: string;

  /**
   * TTL in days for DynamoDB records
   */
  ttlDays: number;

  /**
   * Log level for Lambda functions (AWS Powertools)
   */
  lambdaLogLevel: string;
}

export class Workflow extends Construct {
  public readonly stateMachine: StateMachine;
  public readonly sessionInitializerFunction: Function;

  constructor(scope: Construct, id: string, props: WorkflowProps) {
    super(scope, id);

    this.sessionInitializerFunction = this.createSessionInitializerFunction(props);
    this.stateMachine = this.createStateMachine(props);

    this.applyNagSuppressions();
  }

  private createSessionInitializerFunction(props: WorkflowProps): Function {
    const sessionInitializerFunction = new Function(this, 'SessionInitializer', {
      runtime: Runtime.PYTHON_3_12,
      handler: 'session_initializer.handler',
      code: Code.fromAsset('..', {
        bundling: {
          // Custom bundling: combines handler from infra/lambda with shared code from src/
          image: Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash',
            '-c',
            'cp infra/lambda/session_initializer.py /asset-output/ && ' +
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
          'SessionInitializerPowertoolsLayer',
          `arn:aws:lambda:${Stack.of(this).region}:017000801446:layer:AWSLambdaPowertoolsPythonV3-python312-x86_64:18`,
        ),
      ],
      timeout: Duration.seconds(30),
      memorySize: 256,
      environment: {
        JOURNAL_TABLE_NAME: props.journalTable.tableName,
        TTL_DAYS: props.ttlDays.toString(),
        POWERTOOLS_SERVICE_NAME: 'session-initializer',
        LOG_LEVEL: props.lambdaLogLevel,
      },
      description: 'Lambda function to initialize session by recording SESSION_INITIATED event',
    });

    props.journalTable.grantWriteData(sessionInitializerFunction);

    return sessionInitializerFunction;
  }

  private createStateMachine(props: WorkflowProps): StateMachine {
    const initializeSession = new LambdaInvoke(this, 'InitializeSession', {
      lambdaFunction: this.sessionInitializerFunction,
      resultPath: '$.initResult',
    });

    const invokeAgent = new LambdaInvoke(this, 'InvokeAgent', {
      lambdaFunction: props.agentInvokerFunction,
      resultPath: '$.agentResult',
    });

    const checkStatus = new CallAwsService(this, 'CheckStatus', {
      service: 'dynamodb',
      action: 'query',
      parameters: {
        TableName: props.journalTable.tableName,
        KeyConditionExpression: 'PK = :pk',
        FilterExpression: '#status IN (:completed, :failed)',
        ExpressionAttributeNames: {
          '#status': 'status',
        },
        ExpressionAttributeValues: {
          ':pk': { S: JsonPath.format('SESSION#{}', JsonPath.stringAt('$.session_id')) },
          ':completed': { S: EventStatus.AGENT_BACKGROUND_TASK_COMPLETED },
          ':failed': { S: EventStatus.AGENT_BACKGROUND_TASK_FAILED },
        },
        ScanIndexForward: false, // Most recent events first for faster completion detection
        Limit: 1, // Only need to know if completion event exists
      },
      iamResources: [props.journalTable.tableArn],
      resultPath: '$.queryResult',
    });

    const waitForCompletion = new Wait(this, 'WaitForCompletion', {
      time: WaitTime.duration(Duration.seconds(5)),
    });

    const success = new Succeed(this, 'Success', {
      comment: 'Agent workflow completed successfully',
    });

    const sessionInitFailure = new Fail(this, 'SessionInitializationFailed', {
      comment: 'Failed to initialize session',
      cause: 'Session initializer Lambda function failed',
      error: 'SessionInitializationError',
    });

    const agentInvocationFailure = new Fail(this, 'AgentInvocationFailed', {
      comment: 'Failed to invoke agent',
      cause: 'Agent invoker Lambda function failed',
      error: 'AgentInvocationError',
    });

    const statusCheckFailure = new Fail(this, 'StatusCheckFailed', {
      comment: 'Failed to check agent status',
      cause: 'DynamoDB query for agent status failed',
      error: 'StatusCheckError',
    });

    const agentProcessingFailure = new Fail(this, 'AgentProcessingFailed', {
      comment: 'Agent background task failed',
      cause: `Agent reported ${EventStatus.AGENT_BACKGROUND_TASK_FAILED} status`,
      error: 'AgentProcessingError',
    });

    const evaluateStatus = new Choice(this, 'EvaluateStatus', {
      comment: 'Evaluate agent completion events',
    });

    checkStatus.addCatch(statusCheckFailure);

    evaluateStatus
      .when(
        Condition.and(
          Condition.numberGreaterThan('$.queryResult.Count', 0),
          Condition.stringEquals('$.queryResult.Items[0].status.S', EventStatus.AGENT_BACKGROUND_TASK_COMPLETED),
        ),
        success,
      )
      .when(
        Condition.and(
          Condition.numberGreaterThan('$.queryResult.Count', 0),
          Condition.stringEquals('$.queryResult.Items[0].status.S', EventStatus.AGENT_BACKGROUND_TASK_FAILED),
        ),
        agentProcessingFailure,
      )
      .otherwise(waitForCompletion.next(checkStatus));

    const definition = initializeSession
      .addCatch(sessionInitFailure)
      .next(invokeAgent.addCatch(agentInvocationFailure).next(checkStatus).next(evaluateStatus));

    const logGroup = new LogGroup(this, 'StateMachineLogGroup', {
      logGroupName: `/aws/vendedlogs/states/agent-workflow-${props.environment}`,
      retention: RetentionDays.ONE_MONTH,
    });

    const stateMachine = new StateMachine(this, 'AgentWorkflowStateMachine', {
      definitionBody: DefinitionBody.fromChainable(definition),
      timeout: Duration.minutes(15),
      comment: 'Step Function workflow for agent invocation and status monitoring',
      logs: {
        destination: logGroup,
        level: InfraConfig.stepFunctionsLogLevel,
        includeExecutionData: true,
      },
      tracingEnabled: true,
    });

    this.sessionInitializerFunction.grantInvoke(stateMachine);
    props.agentInvokerFunction.grantInvoke(stateMachine);
    props.journalTable.grantReadData(stateMachine);

    return stateMachine;
  }

  private applyNagSuppressions(): void {
    NagSuppressions.addResourceSuppressions(
      this.sessionInitializerFunction,
      [
        {
          id: 'AwsSolutions-IAM4',
          reason:
            'AWSLambdaBasicExecutionRole is a well-scoped AWS managed policy for Lambda CloudWatch Logs access. Standard practice for Lambda functions.',
        },
        {
          id: 'AwsSolutions-L1',
          reason: 'Python 3.12 is fully supported by AWS Lambda until October 2028.',
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      this.stateMachine,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Lambda function ARN wildcards (`:*`) are added by grantInvoke() to support version and alias invocations. Scoped to specific function ARNs.',
        },
        {
          id: 'AwsSolutions-SF1',
          reason:
            'ERROR level logging is sufficient for production. ALL level logs every state transition and can expose sensitive data in inputs/outputs, increasing costs significantly.',
        },
      ],
      true,
    );
  }
}
