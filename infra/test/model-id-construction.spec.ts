import { beforeEach, describe, expect, it } from 'vitest';

import { type CfnJoin, type PolicyResource, type PolicyStatementJson, createTestStack } from './setup';

describe('Model ID Construction Logic', () => {
  const { template } = createTestStack();
  let invokeStatement: PolicyStatementJson;

  beforeEach(() => {
    const policies = template.findResources('AWS::IAM::Policy', {
      Properties: { PolicyName: 'BedrockModelInvocation' },
    });
    const policy = Object.values(policies)[0] as PolicyResource;
    const statements = policy.Properties.PolicyDocument.Statement;
    invokeStatement = statements.find((stmt) => stmt.Sid === 'InvokeBedrockModel')!;
  });

  const extractModelId = (resources: unknown, pattern: string): string => {
    const resourceArray = resources as unknown[];
    const resource = resourceArray.find((r) => {
      const cfnResource = r as Partial<CfnJoin>;
      if (cfnResource['Fn::Join']) {
        const parts = cfnResource['Fn::Join'][1];
        return parts.some((p) => typeof p === 'string' && p.includes(pattern));
      }
      return false;
    }) as CfnJoin;

    const parts = resource['Fn::Join'][1];
    const modelIdPart = parts.find((p) => typeof p === 'string' && p.includes(pattern)) as string;
    return modelIdPart.split(pattern)[1];
  };

  it('should construct modelId with region prefix when inferenceProfileRegion is set', () => {
    const actualModelId = extractModelId(invokeStatement.Resource, ':inference-profile/');

    expect(actualModelId).toBe('us.anthropic.claude-sonnet-4-20250514-v1:0');
  });

  it('should use base modelId without prefix in foundation model ARN', () => {
    const foundationModelId = extractModelId(invokeStatement.Resource, ':foundation-model/');

    expect(foundationModelId).toBe('anthropic.claude-sonnet-4-20250514-v1:0');
    expect(foundationModelId).not.toContain('us.');
  });
});
