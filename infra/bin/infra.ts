#!/opt/homebrew/opt/node/bin/node
import * as cdk from 'aws-cdk-lib';

import { InfraStack } from '../lib/infra-stack';

const app = new cdk.App();
new InfraStack(app, 'InfraStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
