#!/opt/homebrew/opt/node/bin/node
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';

import { InfraStack } from '../lib/infra-stack';

const app = new cdk.App();
new InfraStack(app, 'InfraStack', {});

cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
