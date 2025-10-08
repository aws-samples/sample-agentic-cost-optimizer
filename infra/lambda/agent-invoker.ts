import { getStringFromEnv, getXRayTraceIdFromEnv } from '@aws-lambda-powertools/commons/utils/env';
import { Logger } from '@aws-lambda-powertools/logger';
import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from '@aws-sdk/client-bedrock-agentcore';

const logger = new Logger({ serviceName: 'agentic-cost-optimizer', logLevel: 'DEBUG' });
const agentCoreClient = new BedrockAgentCoreClient({});
const agentRuntimeArn = getStringFromEnv({ key: 'AGENT_CORE_RUNTIME_ARN' });

export const handler = async (event: { prompt?: string }) => {
  try {
    const response = await agentCoreClient.send(
      new InvokeAgentRuntimeCommand({
        agentRuntimeArn,
        traceId: getXRayTraceIdFromEnv(),
        payload: JSON.stringify({
          prompt: event.prompt ?? 'check any of my Lambda functions and tell me if they are overprovisioned',
        }),
      }),
    );

    logger.info('Agent invoked successfully', { sessionId: response.runtimeSessionId });

    return { status: response.statusCode, sessionId: response.runtimeSessionId };
  } catch (error) {
    logger.error('Error invoking agent:', { error });
    throw error;
  }
};
