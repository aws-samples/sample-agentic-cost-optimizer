import { getStringFromEnv, getXRayTraceIdFromEnv } from '@aws-lambda-powertools/commons/utils/env';
import { Logger } from '@aws-lambda-powertools/logger';
import { BedrockAgentCoreClient, InvokeAgentRuntimeCommand } from '@aws-sdk/client-bedrock-agentcore';

const logger = new Logger({ serviceName: 'agentic-cost-optimizer', logLevel: 'DEBUG' });
const agentCoreClient = new BedrockAgentCoreClient({});
const agentRuntimeArn = getStringFromEnv({ key: 'AGENT_CORE_RUNTIME_ARN' });

export const handler = async (event: { session_id: string; prompt?: string }) => {
  logger.info('Lambda started', { sessionId: event.session_id });

  try {
    logger.info('Calling AgentCore...');

    const response = await agentCoreClient.send(
      new InvokeAgentRuntimeCommand({
        agentRuntimeArn,
        runtimeSessionId: event.session_id, // Keep the session ID for consistency
        traceId: getXRayTraceIdFromEnv(),
        payload: JSON.stringify({
          prompt: event.prompt ?? "Check my resources and let me know if they're overprovisioned",
          session_id: event.session_id,
        }),
      }),
    );

    logger.info('AgentCore responded', { sessionId: response.runtimeSessionId, status: response.statusCode });

    return { status: response.statusCode, sessionId: response.runtimeSessionId };
  } catch (error: any) {
    logger.error('AgentCore failed', { error: error.message, sessionId: event.session_id });
    throw error;
  }
};
