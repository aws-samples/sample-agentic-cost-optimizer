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

/**
 * Gets the Bedrock IAM policy statements from a template
 */
export function getBedrockPolicyStatements(template: Template) {
  const policies = template.findResources('AWS::IAM::Policy', {
    Properties: {
      PolicyName: 'BedrockModelInvocation',
    },
  });
  const policy = Object.values(policies)[0] as any;
  return policy.Properties.PolicyDocument.Statement;
}
