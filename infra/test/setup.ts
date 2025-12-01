import { App } from 'aws-cdk-lib';

import { Template } from 'aws-cdk-lib/assertions';

import { InfraStack } from '../lib/infra-stack';

/**
 * Creates a test stack and template for testing
 */
export function createTestStack() {
  const app = new App();
  const stack = new InfraStack(app, 'TestStack');
  const template = Template.fromStack(stack);

  return { app, stack, template };
}
