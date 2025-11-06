import { Duration, Stack } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { Table } from 'aws-cdk-lib/aws-dynamodb';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Code, Function, LayerVersion, Runtime } from 'aws-cdk-lib/aws-lambda';
import { Choice, Condition, DefinitionBody, Fail, JsonPath, StateMachine, Succeed, Wait, WaitTime } from 'aws-cdk-lib/aws-stepfunctions';
import { CallAwsService, LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';

import { EventStatus } from '../constants/event-statuses';

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
   * Log level for Lambda functions
   */
  logLevel: string;
}

export class Workflow extends Construct {
  public readonly stateMachine: StateMachine;
  public readonly sessionInitializerFunction: Function;

  constructor(scope: Construct, id: string, props: WorkflowProps) {
    super(scope, id);

    // Create session initializer Lambda function
    this.sessionInitializerFunction = this.createSessionInitializerFunction(props);

    // Create the Step Function state machine
    this.stateMachine = this.createStateMachine(props);
  }

  private createSessionInitializerFunction(props: WorkflowProps): Function {
    const sessionInitializerFunction = new Function(this, 'SessionInitializer', {
      runtime: Runtime.PYTHON_3_12,
      handler: 'session_initializer.handler',
      code: Code.fromAsset('..', {
        // Custom bundling: combines handler from infra/lambda with shared code from src/
        bundling: {
          image: Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash',
            '-c',
            'cp infra/lambda/session_initializer.py /asset-output/ && ' +
              'mkdir -p /asset-output/src && ' +
              'rsync -av --exclude="__pycache__" --exclude="*.pyc" src/shared src/__init__.py /asset-output/src/',
          ],
        },
        // Exclude list speeds up CDK asset hash calculation by skipping large/irrelevant directories
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
        // AWS Lambda Powertools Layer - version 18 for Python 3.12 x86_64
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
        LOG_LEVEL: props.logLevel,
      },
      description: 'Lambda function to initialize session by recording SESSION_INITIATED event',
    });

    // Grant Lambda permission to write events to DynamoDB
    props.journalTable.grantWriteData(sessionInitializerFunction);

    return sessionInitializerFunction;
  }

  private createStateMachine(props: WorkflowProps): StateMachine {
    // Define session initialization task - invoke Lambda to record SESSION_INITIATED event
    const initializeSession = new LambdaInvoke(this, 'InitializeSession', {
      lambdaFunction: this.sessionInitializerFunction,
      resultPath: '$.initResult',
    });

    // Define the Lambda invocation task
    const invokeAgent = new LambdaInvoke(this, 'InvokeAgent', {
      lambdaFunction: props.agentInvokerFunction,
      resultPath: '$.agentResult',
    });

    // Define DynamoDB query task to check for completion events
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
        ScanIndexForward: false, // Get most recent events first
        Limit: 1, // We only need to know if one exists
      },
      iamResources: [props.journalTable.tableArn],
      resultPath: '$.queryResult',
    });

    // Define wait state for polling
    const waitForCompletion = new Wait(this, 'WaitForCompletion', {
      time: WaitTime.duration(Duration.seconds(5)),
    });

    // Define success state
    const success = new Succeed(this, 'Success', {
      comment: 'Agent workflow completed successfully',
    });

    // Define specific failure states for better error tracking
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

    // Define choice logic for status evaluation
    const evaluateStatus = new Choice(this, 'EvaluateStatus', {
      comment: 'Evaluate agent completion events',
    });

    // Add error handling to checkStatus once
    checkStatus.addCatch(statusCheckFailure);

    // Check if query returned any completion events
    // If Count > 0, we have a completion event - check which one
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

    // Chain the states together - start with session initialization
    const definition = initializeSession
      .addCatch(sessionInitFailure)
      .next(invokeAgent.addCatch(agentInvocationFailure).next(checkStatus).next(evaluateStatus));

    // Create the state machine
    const stateMachine = new StateMachine(this, 'AgentWorkflowStateMachine', {
      definitionBody: DefinitionBody.fromChainable(definition),
      timeout: Duration.minutes(15),
      comment: 'Step Function workflow for agent invocation and status monitoring',
    });

    // Grant permissions to invoke Lambda functions
    stateMachine.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['lambda:InvokeFunction'],
        resources: [this.sessionInitializerFunction.functionArn, props.agentInvokerFunction.functionArn],
      }),
    );

    // Grant permissions to query DynamoDB table (PutItem now handled by Lambda)
    stateMachine.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['dynamodb:Query'],
        resources: [props.journalTable.tableArn],
      }),
    );

    return stateMachine;
  }
}
