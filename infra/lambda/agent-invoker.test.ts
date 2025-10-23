import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from '@aws-sdk/client-bedrock-agentcore';
import { mockClient } from 'aws-sdk-client-mock';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { handler } from './agent-invoker';

// Mock AWS Lambda Powertools
vi.mock('@aws-lambda-powertools/commons/utils/env', () => ({
  getStringFromEnv: vi.fn(() => 'mock-agent-runtime-arn'),
  getXRayTraceIdFromEnv: vi.fn(() => 'mock-trace-id'),
}));

vi.mock('@aws-lambda-powertools/logger', () => ({
  Logger: class MockLogger {
    info = vi.fn();
    error = vi.fn();
    constructor(config: any) {}
  },
}));

// Create mock client
const mockBedrockClient = mockClient(BedrockAgentCoreClient);

describe('agent-invoker handler', () => {
  beforeEach(() => {
    mockBedrockClient.reset();
  });

  it('should successfully invoke agent with default prompt', async () => {
    // Arrange
    const mockEvent = { session_id: 'test-session-123' };
    const mockResponse = {
      statusCode: 200,
      runtimeSessionId: 'test-session-123',
    };
    mockBedrockClient.on(InvokeAgentRuntimeCommand).resolves(mockResponse);

    // Act
    const result = await handler(mockEvent);

    // Assert
    expect(result).toEqual({
      status: 200,
      sessionId: 'test-session-123',
    });
    expect(mockBedrockClient.commandCalls(InvokeAgentRuntimeCommand)).toHaveLength(1);
    expect(mockBedrockClient.commandCalls(InvokeAgentRuntimeCommand)[0].args[0].input).toMatchObject({
      agentRuntimeArn: 'mock-agent-runtime-arn',
      runtimeSessionId: 'test-session-123',
      traceId: 'mock-trace-id',
      payload: JSON.stringify({
        prompt: "Check my resources and let me know if they're overprovisioned",
        session_id: 'test-session-123',
      }),
    });
  });

  it('should successfully invoke agent with custom prompt', async () => {
    // Arrange
    const mockEvent = {
      session_id: 'test-session-456',
      prompt: 'Custom optimization request',
    };
    const mockResponse = {
      statusCode: 200,
      runtimeSessionId: 'test-session-456',
    };
    mockBedrockClient.on(InvokeAgentRuntimeCommand).resolves(mockResponse);

    // Act
    const result = await handler(mockEvent);

    // Assert
    expect(result).toEqual({
      status: 200,
      sessionId: 'test-session-456',
    });
    expect(mockBedrockClient.commandCalls(InvokeAgentRuntimeCommand)).toHaveLength(1);
    expect(mockBedrockClient.commandCalls(InvokeAgentRuntimeCommand)[0].args[0].input).toMatchObject({
      agentRuntimeArn: 'mock-agent-runtime-arn',
      runtimeSessionId: 'test-session-456',
      traceId: 'mock-trace-id',
      payload: JSON.stringify({
        prompt: 'Custom optimization request',
        session_id: 'test-session-456',
      }),
    });
  });

  it('should handle AgentCore errors gracefully', async () => {
    // Arrange
    const mockEvent = { session_id: 'test-session-error' };
    const mockError = new Error('AgentCore service unavailable');
    mockBedrockClient.on(InvokeAgentRuntimeCommand).rejects(mockError);

    // Act & Assert
    await expect(handler(mockEvent)).rejects.toThrow('AgentCore service unavailable');
    expect(mockBedrockClient.commandCalls(InvokeAgentRuntimeCommand)).toHaveLength(1);
    expect(mockBedrockClient.commandCalls(InvokeAgentRuntimeCommand)[0].args[0].input).toMatchObject({
      agentRuntimeArn: 'mock-agent-runtime-arn',
      runtimeSessionId: 'test-session-error',
      traceId: 'mock-trace-id',
      payload: JSON.stringify({
        prompt: "Check my resources and let me know if they're overprovisioned",
        session_id: 'test-session-error',
      }),
    });
  });

  it('should handle different status codes from AgentCore', async () => {
    // Arrange
    const mockEvent = { session_id: 'test-session-partial' };
    const mockResponse = {
      statusCode: 202,
      runtimeSessionId: 'test-session-partial',
    };
    mockBedrockClient.on(InvokeAgentRuntimeCommand).resolves(mockResponse);

    // Act
    const result = await handler(mockEvent);

    // Assert
    expect(result).toEqual({
      status: 202,
      sessionId: 'test-session-partial',
    });
  });
});
