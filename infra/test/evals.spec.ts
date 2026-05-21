import { App, Stack } from 'aws-cdk-lib';
import { describe, expect, it } from 'vitest';

import { Match, Template } from 'aws-cdk-lib/assertions';

import { EvalsConfig } from '../constants/evals-config';
import { Agent } from '../lib/agent';
import { Evals } from '../lib/evals';
import { InfraStack } from '../lib/infra-stack';

const ONLINE_EVAL_RESOURCE_TYPE = 'AWS::BedrockAgentCore::OnlineEvaluationConfig';

function createEvalsTestStack() {
  const app = new App();
  const stack = new Stack(app, 'TestStack', {
    env: { account: '123456789012', region: 'us-east-1' },
  });

  const agent = new Agent(stack, 'TestAgent', {
    agentRuntimeName: 'testRuntime_dev_v1',
    description: 'Test agent for evals testing',
    environment: 'dev',
    modelId: 'anthropic.claude-sonnet-4-5-20250929-v1:0',
    inferenceProfileRegion: 'us',
  });

  new Evals(stack, 'TestEvals', { agent, environment: 'dev' });

  return Template.fromStack(stack);
}

describe('Evals Construct', () => {
  it('creates an OnlineEvaluationConfig resource', () => {
    const template = createEvalsTestStack();
    template.resourceCountIs(ONLINE_EVAL_RESOURCE_TYPE, 1);
  });

  it('names the config using getEvalsConfigName(environment)', () => {
    const template = createEvalsTestStack();
    template.hasResourceProperties(ONLINE_EVAL_RESOURCE_TYPE, {
      OnlineEvaluationConfigName: 'cost_optimizer_eval_dev',
    });
  });

  it('configures all builtin evaluators from EvalsConfig', () => {
    const template = createEvalsTestStack();
    const expectedEvaluators = EvalsConfig.evaluators.map((e) => Match.objectLike({ EvaluatorId: e.value }));
    template.hasResourceProperties(ONLINE_EVAL_RESOURCE_TYPE, {
      Evaluators: Match.arrayWith(expectedEvaluators),
    });
  });
});

describe('InfraStack conditional Evals creation', () => {
  function buildStack(enableEvals: boolean) {
    const app = new App();
    return new InfraStack(app, 'TestStack', {
      environment: 'dev',
      runtimeVersion: 'v2',
      enableScheduledTrigger: false,
      enableManualTrigger: false,
      enableEvals,
    });
  }

  it('creates Evals and outputs when enableEvals=true', () => {
    const stack = buildStack(true);
    const template = Template.fromStack(stack);

    expect(stack.evals).toBeDefined();
    template.resourceCountIs(ONLINE_EVAL_RESOURCE_TYPE, 1);

    const outputKeys = Object.keys(template.findOutputs('*'));
    expect(outputKeys.some((k) => k.includes('EvaluationConfigId'))).toBe(true);
    expect(outputKeys.some((k) => k.includes('EvaluationConfigArn'))).toBe(true);
  });

  it('omits Evals and outputs when enableEvals=false', () => {
    const stack = buildStack(false);
    const template = Template.fromStack(stack);

    expect(stack.evals).toBeUndefined();
    template.resourceCountIs(ONLINE_EVAL_RESOURCE_TYPE, 0);

    const outputKeys = Object.keys(template.findOutputs('*'));
    expect(outputKeys.some((k) => k.includes('EvaluationConfigId'))).toBe(false);
    expect(outputKeys.some((k) => k.includes('EvaluationConfigArn'))).toBe(false);
  });
});
