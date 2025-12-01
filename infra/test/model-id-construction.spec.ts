import { describe, expect, it } from 'vitest';

import { createTestStack, getBedrockPolicyStatements } from './setup';

describe('Model ID Construction Logic', () => {
  const { template } = createTestStack();

  it('should construct modelId with region prefix when inferenceProfileRegion is set', () => {
    const statements = getBedrockPolicyStatements(template);
    const invokeStatement = statements.find((stmt: any) => stmt.Sid === 'InvokeBedrockModel');

    const inferenceProfileResource = invokeStatement.Resource.find((r: any) => {
      if (r['Fn::Join']) {
        const parts = r['Fn::Join'][1];
        return parts.some((p: any) => typeof p === 'string' && p.includes(':inference-profile/'));
      }
      return false;
    });

    const parts = inferenceProfileResource['Fn::Join'][1];
    const modelIdPart = parts.find((p: any) => typeof p === 'string' && p.includes(':inference-profile/'));
    const actualModelId = modelIdPart.split(':inference-profile/')[1];

    expect(actualModelId).toBe('us.anthropic.claude-sonnet-4-20250514-v1:0');
  });

  it('should use base modelId without prefix in foundation model ARN', () => {
    const statements = getBedrockPolicyStatements(template);
    const invokeStatement = statements.find((stmt: any) => stmt.Sid === 'InvokeBedrockModel');

    const foundationModelResource = invokeStatement.Resource.find((r: any) => {
      if (r['Fn::Join']) {
        const parts = r['Fn::Join'][1];
        return parts.some((p: any) => typeof p === 'string' && p.includes(':foundation-model/'));
      }
      return false;
    });

    const parts = foundationModelResource['Fn::Join'][1];
    const modelIdPart = parts.find((p: any) => typeof p === 'string' && p.includes(':foundation-model/'));
    const foundationModelId = modelIdPart.split(':foundation-model/')[1];

    expect(foundationModelId).toBe('anthropic.claude-sonnet-4-20250514-v1:0');
    expect(foundationModelId).not.toContain('us.');
  });
});
