#!/opt/homebrew/opt/node/bin/node
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';

import { InfraConfig } from '../constants/infra-config';
import { InfraStack } from '../lib/infra-stack';

const app = new cdk.App();
const environment = process.env.ENVIRONMENT || 'dev';
const runtimeVersion = process.env.RUNTIME_VERSION || 'v2';

new InfraStack(app, 'InfraStack', {
  description: InfraConfig.stackDescription,
  environment,
  runtimeVersion,
  enableManualTrigger: environment === 'dev',
});

cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
