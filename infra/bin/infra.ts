#!/opt/homebrew/opt/node/bin/node
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';

import { InfraConfig } from '../constants/infra-config';
import { InfraStack } from '../lib/infra-stack';

const app = new cdk.App();
const environment = process.env.ENVIRONMENT || 'dev';
const runtimeVersion = process.env.RUNTIME_VERSION || 'v2';

// Enable evals: default to true only for prod, allow override via env var or context
const enableEvalsEnv = process.env.ENABLE_EVALS;
const enableEvalsContext = app.node.tryGetContext('enableEvals');
const enableEvals =
  enableEvalsEnv !== undefined
    ? enableEvalsEnv === 'true'
    : enableEvalsContext !== undefined
      ? enableEvalsContext === true || enableEvalsContext === 'true'
      : environment === 'prod';

// Enable scheduled trigger: default to true only for prod
const enableScheduledTriggerEnv = process.env.ENABLE_SCHEDULED_TRIGGER;
const enableScheduledTrigger = enableScheduledTriggerEnv !== undefined ? enableScheduledTriggerEnv === 'true' : environment === 'prod';

new InfraStack(app, 'InfraStack', {
  description: InfraConfig.stackDescription,
  environment,
  runtimeVersion,
  enableScheduledTrigger,
  enableManualTrigger: environment !== 'prod', // dev and staging get manual trigger, prod does not
  enableEvals,
});

cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
