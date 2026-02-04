import { App } from 'aws-cdk-lib';

import { Template } from 'aws-cdk-lib/assertions';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';

import { InfraStack } from '../lib/infra-stack';

export type PolicyStatementJson = ReturnType<PolicyStatement['toJSON']>;

export interface PolicyResource {
  Properties: {
    PolicyDocument: {
      Statement: PolicyStatementJson[];
    };
  };
}

export interface CfnJoin {
  'Fn::Join': [string, unknown[]];
}

/**
 * Creates a test stack and template for testing
 */
export function createTestStack(enableManualTrigger = true) {
  const app = new App();
  const stack = new InfraStack(app, 'TestStack', {
    environment: 'dev',
    runtimeVersion: 'v2',
    enableScheduledTrigger: true,
    enableManualTrigger,
    enableEvals: false,
  });
  const template = Template.fromStack(stack);

  return { app, stack, template };
}
