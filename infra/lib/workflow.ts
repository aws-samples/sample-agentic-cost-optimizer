import { Duration } from 'aws-cdk-lib';
import { Construct } from 'constructs';

import { Table } from 'aws-cdk-lib/aws-dynamodb';
import { Effect, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Function as LambdaFunction } from 'aws-cdk-lib/aws-lambda';
import { Choice, Condition, DefinitionBody, Fail, JsonPath, StateMachine, Succeed, Wait, WaitTime } from 'aws-cdk-lib/aws-stepfunctions';
import { DynamoAttributeValue, DynamoGetItem, DynamoPutItem, LambdaInvoke } from 'aws-cdk-lib/aws-stepfunctions-tasks';

export interface WorkflowProps {
  /**
   * The Lambda function that invokes the agent
   */
  agentInvokerFunction: LambdaFunction;

  /**
   * The DynamoDB table for session journaling
   */
  journalTable: Table;
}

export class Workflow extends Construct {
  public readonly stateMachine: StateMachine;

  constructor(scope: Construct, id: string, props: WorkflowProps) {
    super(scope, id);

    // Create the Step Function state machine
    this.stateMachine = this.createStateMachine(props);
  }

  private createStateMachine(props: WorkflowProps): StateMachine {
    // Define session initialization task
    const createSessionRecord = new DynamoPutItem(this, 'CreateSessionRecord', {
      table: props.journalTable,
      item: {
        PK: DynamoAttributeValue.fromString(JsonPath.stringAt('$.session_id')),
        SK: DynamoAttributeValue.fromString('SESSION'),
        status: DynamoAttributeValue.fromString('INITIATED'),
        created_at: DynamoAttributeValue.fromString(JsonPath.stateEnteredTime),
      },
      resultPath: '$.initResult',
    });

    // Define the Lambda invocation task
    const invokeAgent = new LambdaInvoke(this, 'InvokeAgent', {
      lambdaFunction: props.agentInvokerFunction,
      resultPath: '$.agentResult',
    });

    // Define DynamoDB status check task
    const checkStatus = new DynamoGetItem(this, 'CheckStatus', {
      table: props.journalTable,
      key: {
        PK: DynamoAttributeValue.fromString(JsonPath.stringAt('$.session_id')),
        SK: DynamoAttributeValue.fromString('SESSION'),
      },
      resultPath: '$.statusResult',
    });

    // Define wait state for polling
    const waitForCompletion = new Wait(this, 'WaitForCompletion', {
      time: WaitTime.duration(Duration.seconds(5)),
    });

    // Define success state
    const success = new Succeed(this, 'Success', {
      comment: 'Agent workflow completed successfully',
    });

    // Define failure state
    const failure = new Fail(this, 'Failure', {
      comment: 'Agent workflow failed',
      cause: 'Agent processing failed or Lambda invocation failed',
    });

    // Define choice logic for status evaluation
    const evaluateStatus = new Choice(this, 'EvaluateStatus', {
      comment: 'Evaluate agent session status',
    });

    // Add conditions for status evaluation - using DynamoDB native format
    evaluateStatus
      .when(Condition.stringEquals('$.statusResult.Item.status.S', 'COMPLETED'), success)
      .when(Condition.stringEquals('$.statusResult.Item.status.S', 'FAILED'), failure)
      .when(
        Condition.or(
          Condition.stringEquals('$.statusResult.Item.status.S', 'INITIATED'),
          Condition.stringEquals('$.statusResult.Item.status.S', 'BUSY'),
        ),
        waitForCompletion.next(checkStatus),
      )
      .otherwise(failure);

    // Chain the states together - start with session initialization
    const definition = createSessionRecord.addCatch(failure).next(invokeAgent.addCatch(failure).next(checkStatus).next(evaluateStatus));

    // Create the state machine
    const stateMachine = new StateMachine(this, 'AgentWorkflowStateMachine', {
      definitionBody: DefinitionBody.fromChainable(definition),
      timeout: Duration.minutes(15),
      comment: 'Step Function workflow for agent invocation and status monitoring',
    });

    // Grant permissions to invoke Lambda function
    stateMachine.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['lambda:InvokeFunction'],
        resources: [props.agentInvokerFunction.functionArn],
      }),
    );

    // Grant permissions to read from and write to DynamoDB table
    stateMachine.addToRolePolicy(
      new PolicyStatement({
        effect: Effect.ALLOW,
        actions: ['dynamodb:GetItem', 'dynamodb:PutItem'],
        resources: [props.journalTable.tableArn],
      }),
    );

    return stateMachine;
  }
}
