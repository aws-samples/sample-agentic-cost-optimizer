import { Duration } from 'aws-cdk-lib';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

import { DataSourceConfig, EvaluatorSelector, ExecutionStatus, OnlineEvaluationConfig } from 'aws-cdk-lib/aws-bedrockagentcore';

import { EvalsConfig, getEvalsConfigName } from '../constants/evals-config';
import { Agent } from './agent';

export interface EvalsProps {
  /**
   * The Agent construct to evaluate
   */
  agent: Agent;

  /**
   * Environment name (used in config naming)
   */
  environment: string;
}

/**
 * Wrapper around the AgentCore OnlineEvaluationConfig L2.
 *
 * Kept as a thin construct (rather than inlining) for symmetry with Agent and
 * Workflow, and as the natural home for future custom Evaluator instances.
 */
export class Evals extends Construct {
  public readonly config: OnlineEvaluationConfig;
  public readonly configId: string;
  public readonly configArn: string;

  constructor(scope: Construct, id: string, props: EvalsProps) {
    super(scope, id);

    const { agent, environment } = props;

    // executionStatus must be set explicitly: the underlying CFN resource defaults to DISABLED,
    // which deploys the config but prevents evaluators from running.
    // samplingPercentage and sessionTimeout override L2 defaults (10% / 15min) because those
    // produced no observable evals on dev traffic; revisit if eval cost becomes meaningful.
    this.config = new OnlineEvaluationConfig(this, 'Config', {
      onlineEvaluationConfigName: getEvalsConfigName(environment),
      evaluators: EvalsConfig.evaluators.map((evaluator) => EvaluatorSelector.builtin(evaluator)),
      dataSource: DataSourceConfig.fromAgentRuntimeEndpoint(agent.runtime),
      executionStatus: ExecutionStatus.ENABLED,
      samplingPercentage: 100,
      sessionTimeout: Duration.minutes(5),
    });

    this.configId = this.config.onlineEvaluationConfigId;
    this.configArn = this.config.onlineEvaluationConfigArn;

    NagSuppressions.addResourceSuppressions(
      this.config,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Wildcards on the auto-generated execution role are required to invoke any Bedrock foundation model and to query CloudWatch log groups whose names are tokens at synth time. Policies are emitted by aws-cdk-lib/aws-bedrockagentcore.',
        },
      ],
      true,
    );
  }
}
