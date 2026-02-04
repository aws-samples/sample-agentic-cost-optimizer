import { LogLevel } from 'aws-cdk-lib/aws-stepfunctions';

/**
 * Infrastructure configuration constants
 */

/**
 * Bedrock cross-region inference profile options
 */
export type CrossRegionProfile = 'us' | 'eu' | 'apac' | 'global' | null;

export const InfraConfig = {
  /**
   * Bedrock model ID to use for the agent
   * Default: Claude Sonnet 4.5
   * Note: Do not include region prefix (us./eu.) - use crossRegionInferenceProfile instead
   */
  modelId: 'anthropic.claude-sonnet-4-5-20250929-v1:0',

  /**
   * Bedrock cross-region inference profile prefix
   * Options:
   * - 'us': US cross-region (routes across US regions)
   * - 'eu': EU cross-region (routes across EU regions)
   * - 'apac': Asia Pacific cross-region (routes across APAC regions)
   * - 'global': Global cross-region (routes across ALL commercial AWS regions)
   * - null: Single-region model (no cross-region routing)
   */
  inferenceProfileRegion: 'us' as CrossRegionProfile,

  /**
   * DynamoDB TTL retention period in days
   * Events older than this will be automatically deleted
   */
  ttlDays: 30,

  /**
   * Log level for Lambda functions (AWS Powertools)
   * Options: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
   */
  lambdaLogLevel: 'DEBUG',

  /**
   * Step Functions log level
   * Options: LogLevel.ALL (verbose), LogLevel.ERROR (failures only), LogLevel.FATAL (execution failures), LogLevel.OFF (no logging)
   */
  stepFunctionsLogLevel: LogLevel.ERROR,

  /**
   * Service name for AWS Lambda Powertools
   * Used for structured logging and tracing
   */
  serviceName: 'agentic-cost-optimizer',

  /**
   * Stack description for CloudFormation
   */
  stackDescription: 'Agent Core infrastructure stack (uksb-d7u5xm7tro).',
} as const;
