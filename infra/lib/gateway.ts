import {
  Gateway as AgentCoreGateway,
  GatewayAuthorizer,
  GatewayExceptionLevel,
  SchemaDefinitionType,
  ToolSchema,
} from '@aws-cdk/aws-bedrock-agentcore-alpha';
import * as cdk from 'aws-cdk-lib';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

import * as bedrockagentcore from 'aws-cdk-lib/aws-bedrockagentcore';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { IBucket } from 'aws-cdk-lib/aws-s3';

export interface GatewayProps {
  agentDataBucket: IBucket;
  journalTableName: string;
  journalTableArn: string;
  ttlDays: number;
  environment: string;
}

export class Gateway extends Construct {
  public readonly gatewayUrl: string;
  public readonly tokenEndpoint: string;
  public readonly clientId: string;
  public readonly clientSecret: cdk.SecretValue;
  public readonly scope: string;

  constructor(scope: Construct, id: string, props: GatewayProps) {
    super(scope, id);

    const stack = cdk.Stack.of(this);
    const { agentDataBucket, journalTableName, journalTableArn, ttlDays, environment } = props;
    const gatewayName = `cost-optimizer-gw-${environment}`;

    // Cognito — full OAuth2 client credentials setup
    const userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: `${gatewayName}-userpool`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const resourceServer = userPool.addResourceServer('ResourceServer', {
      identifier: gatewayName,
      scopes: [{ scopeName: 'invoke', scopeDescription: 'Invoke gateway tools' }],
    });

    const userPoolClient = userPool.addClient('Client', {
      userPoolClientName: `${gatewayName}-client`,
      generateSecret: true,
      oAuth: {
        flows: { clientCredentials: true },
        scopes: [cognito.OAuthScope.custom(`${gatewayName}/invoke`)],
      },
    });
    userPoolClient.node.addDependency(resourceServer);

    const userPoolDomain = userPool.addDomain('Domain', {
      cognitoDomain: { domainPrefix: `${gatewayName}-${cdk.Aws.ACCOUNT_ID}` },
    });

    // Storage Lambda — scoped S3 permissions only
    const storageRole = new iam.Role(this, 'StorageLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')],
    });
    agentDataBucket.grantReadWrite(storageRole);

    const storageFunction = new lambda.Function(this, 'StorageFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'storage_tool.lambda_handler',
      code: lambda.Code.fromAsset('lambda'),
      role: storageRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        S3_BUCKET_NAME: agentDataBucket.bucketName,
      },
    });

    // Interceptor Lambda
    const interceptorFunction = new lambda.Function(this, 'InterceptorFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'interceptor.lambda_handler',
      code: lambda.Code.fromAsset('lambda'),
      timeout: cdk.Duration.seconds(10),
      memorySize: 256,
    });

    // L2 Gateway with our Cognito authorizer
    const gateway = new AgentCoreGateway(this, 'AgentCoreGateway', {
      gatewayName,
      description: 'Gateway for cost optimizer agent tools',
      exceptionLevel: GatewayExceptionLevel.DEBUG,
      authorizerConfiguration: GatewayAuthorizer.usingCognito({
        userPool,
        allowedClients: [userPoolClient],
      }),
    });

    // Escape hatch: interceptor config (not yet in L2)
    const cfnGateway = gateway.node.defaultChild as bedrockagentcore.CfnGateway;

    interceptorFunction.addPermission('GatewayInterceptorInvoke', {
      principal: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      action: 'lambda:InvokeFunction',
    });

    gateway.role.attachInlinePolicy(
      new iam.Policy(this, 'InterceptorInvokePolicy', {
        statements: [
          new iam.PolicyStatement({
            actions: ['lambda:InvokeFunction'],
            resources: [interceptorFunction.functionArn],
          }),
        ],
      }),
    );

    cfnGateway.addPropertyOverride('InterceptorConfigurations', [
      {
        InterceptionPoints: ['REQUEST', 'RESPONSE'],
        Interceptor: {
          Lambda: {
            Arn: interceptorFunction.functionArn,
          },
        },
      },
    ]);

    // Storage Lambda target
    gateway.addLambdaTarget('StorageTarget', {
      gatewayTargetName: 'StorageTool',
      description: 'S3 storage read/write tools',
      lambdaFunction: storageFunction,
      toolSchema: ToolSchema.fromInline([
        {
          name: 'storage_read',
          description: 'Read a file from S3 storage for the current session',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              filename: {
                type: SchemaDefinitionType.STRING,
                description: 'Name of the file to read',
              },
            },
            required: ['filename'],
          },
        },
        {
          name: 'storage_write',
          description: 'Write a file to S3 storage for the current session',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              filename: {
                type: SchemaDefinitionType.STRING,
                description: 'Name of the file to write',
              },
              content: {
                type: SchemaDefinitionType.STRING,
                description: 'Text content to write',
              },
            },
            required: ['filename', 'content'],
          },
        },
      ]),
    });

    // Journal Lambda — uses dist/build-lambda which includes shared/ at root level
    const journalRole = new iam.Role(this, 'JournalLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')],
      inlinePolicies: {
        JournalDynamoDB: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['dynamodb:PutItem'],
              resources: [journalTableArn],
            }),
          ],
        }),
      },
    });

    const journalFunction = new lambda.Function(this, 'JournalFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'journal_tool.lambda_handler',
      code: lambda.Code.fromAsset('dist/build-lambda'),
      role: journalRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        JOURNAL_TABLE_NAME: journalTableName,
        TTL_DAYS: ttlDays.toString(),
      },
    });

    // Journal Lambda target
    gateway.addLambdaTarget('JournalTarget', {
      gatewayTargetName: 'JournalTool',
      description: 'DynamoDB journal start/complete task tools',
      lambdaFunction: journalFunction,
      toolSchema: ToolSchema.fromInline([
        {
          name: 'journal_start_task',
          description: 'Start tracking a new task/phase in the journal',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              phase_name: {
                type: SchemaDefinitionType.STRING,
                description: 'Name of the task/phase to start',
              },
            },
            required: ['phase_name'],
          },
        },
        {
          name: 'journal_complete_task',
          description: 'Complete a task/phase in the journal',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              phase_name: {
                type: SchemaDefinitionType.STRING,
                description: 'Name of the task/phase to complete',
              },
              status: {
                type: SchemaDefinitionType.STRING,
                description: 'Completion status: COMPLETED or FAILED',
              },
              error_message: {
                type: SchemaDefinitionType.STRING,
                description: 'Error message for failed completions',
              },
            },
            required: ['phase_name'],
          },
        },
      ]),
    });

    // Lambda Discovery — read-only Lambda metadata
    const lambdaDiscoveryRole = new iam.Role(this, 'LambdaDiscoveryRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')],
      inlinePolicies: {
        LambdaReadOnly: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['lambda:ListFunctions', 'lambda:GetFunction', 'lambda:GetFunctionConfiguration'],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    const lambdaDiscoveryFunction = new lambda.Function(this, 'LambdaDiscoveryFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'lambda_discovery_tool.lambda_handler',
      code: lambda.Code.fromAsset('lambda'),
      role: lambdaDiscoveryRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    gateway.addLambdaTarget('LambdaDiscoveryTarget', {
      gatewayTargetName: 'LambdaDiscoveryTool',
      description: 'Lambda function discovery and configuration read tools',
      lambdaFunction: lambdaDiscoveryFunction,
      toolSchema: ToolSchema.fromInline([
        {
          name: 'lambda_list_functions',
          description: 'List all Lambda functions with their configurations',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              marker: {
                type: SchemaDefinitionType.STRING,
                description: 'Pagination marker from a previous response',
              },
            },
          },
        },
        {
          name: 'lambda_get_function',
          description: 'Get detailed information about a specific Lambda function',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              function_name: {
                type: SchemaDefinitionType.STRING,
                description: 'Name or ARN of the Lambda function',
              },
            },
            required: ['function_name'],
          },
        },
        {
          name: 'lambda_get_function_configuration',
          description: 'Get configuration details for a specific Lambda function',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              function_name: {
                type: SchemaDefinitionType.STRING,
                description: 'Name or ARN of the Lambda function',
              },
            },
            required: ['function_name'],
          },
        },
      ]),
    });

    // CloudWatch Metrics — read-only metrics access
    const cloudwatchMetricsRole = new iam.Role(this, 'CloudWatchMetricsRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')],
      inlinePolicies: {
        CloudWatchMetricsReadOnly: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['cloudwatch:GetMetricStatistics', 'cloudwatch:ListMetrics'],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    const cloudwatchMetricsFunction = new lambda.Function(this, 'CloudWatchMetricsFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'cloudwatch_metrics_tool.lambda_handler',
      code: lambda.Code.fromAsset('lambda'),
      role: cloudwatchMetricsRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    gateway.addLambdaTarget('CloudWatchMetricsTarget', {
      gatewayTargetName: 'CloudWatchMetricsTool',
      description: 'CloudWatch Metrics read tools',
      lambdaFunction: cloudwatchMetricsFunction,
      toolSchema: ToolSchema.fromInline([
        {
          name: 'cloudwatch_get_metric_statistics',
          description: 'Get metric statistics from CloudWatch for a specific metric',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              namespace: {
                type: SchemaDefinitionType.STRING,
                description: 'CloudWatch namespace (e.g., AWS/Lambda)',
              },
              metric_name: {
                type: SchemaDefinitionType.STRING,
                description: 'Name of the metric (e.g., Invocations, Duration, Errors)',
              },
              start_time: {
                type: SchemaDefinitionType.STRING,
                description: 'Start time in ISO 8601 format',
              },
              end_time: {
                type: SchemaDefinitionType.STRING,
                description: 'End time in ISO 8601 format',
              },
              period: {
                type: SchemaDefinitionType.INTEGER,
                description: 'Period in seconds for data aggregation',
              },
              statistics: {
                type: SchemaDefinitionType.ARRAY,
                description: 'List of statistics to retrieve (e.g., Average, Sum, Maximum)',
                items: { type: SchemaDefinitionType.STRING },
              },
              dimensions: {
                type: SchemaDefinitionType.ARRAY,
                description: 'List of dimensions to filter by',
                items: {
                  type: SchemaDefinitionType.OBJECT,
                  properties: {
                    name: { type: SchemaDefinitionType.STRING, description: 'Dimension name' },
                    value: { type: SchemaDefinitionType.STRING, description: 'Dimension value' },
                  },
                  required: ['name', 'value'],
                },
              },
            },
            required: ['namespace', 'metric_name', 'start_time', 'end_time', 'period', 'statistics'],
          },
        },
        {
          name: 'cloudwatch_list_metrics',
          description: 'List available CloudWatch metrics with optional filters',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              namespace: {
                type: SchemaDefinitionType.STRING,
                description: 'CloudWatch namespace to filter by (e.g., AWS/Lambda)',
              },
              metric_name: {
                type: SchemaDefinitionType.STRING,
                description: 'Metric name to filter by',
              },
              dimensions: {
                type: SchemaDefinitionType.ARRAY,
                description: 'Dimensions to filter by',
                items: {
                  type: SchemaDefinitionType.OBJECT,
                  properties: {
                    name: { type: SchemaDefinitionType.STRING, description: 'Dimension name' },
                    value: { type: SchemaDefinitionType.STRING, description: 'Dimension value' },
                  },
                  required: ['name'],
                },
              },
            },
          },
        },
      ]),
    });

    // CloudWatch Logs — Insights query access scoped to Lambda log groups
    const cloudwatchLogsRole = new iam.Role(this, 'CloudWatchLogsRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')],
      inlinePolicies: {
        CloudWatchLogsQuery: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['logs:StartQuery'],
              resources: [`arn:${stack.partition}:logs:*:*:log-group:/aws/lambda/*`],
            }),
            new iam.PolicyStatement({
              actions: ['logs:GetQueryResults', 'logs:StopQuery'],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    const cloudwatchLogsFunction = new lambda.Function(this, 'CloudWatchLogsFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'cloudwatch_logs_tool.lambda_handler',
      code: lambda.Code.fromAsset('lambda'),
      role: cloudwatchLogsRole,
      timeout: cdk.Duration.seconds(60),
      memorySize: 256,
    });

    gateway.addLambdaTarget('CloudWatchLogsTarget', {
      gatewayTargetName: 'CloudWatchLogsTool',
      description: 'CloudWatch Logs Insights query tools',
      lambdaFunction: cloudwatchLogsFunction,
      toolSchema: ToolSchema.fromInline([
        {
          name: 'cloudwatch_start_query',
          description: 'Start a CloudWatch Logs Insights query',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              log_group_name: {
                type: SchemaDefinitionType.STRING,
                description: 'Name of the CloudWatch log group to query',
              },
              query_string: {
                type: SchemaDefinitionType.STRING,
                description: 'CloudWatch Logs Insights query string',
              },
              start_time: {
                type: SchemaDefinitionType.INTEGER,
                description: 'Start time as Unix timestamp in seconds',
              },
              end_time: {
                type: SchemaDefinitionType.INTEGER,
                description: 'End time as Unix timestamp in seconds',
              },
            },
            required: ['log_group_name', 'query_string', 'start_time', 'end_time'],
          },
        },
        {
          name: 'cloudwatch_get_query_results',
          description: 'Get results of a CloudWatch Logs Insights query',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              query_id: {
                type: SchemaDefinitionType.STRING,
                description: 'Query ID returned by cloudwatch_start_query',
              },
            },
            required: ['query_id'],
          },
        },
        {
          name: 'cloudwatch_stop_query',
          description: 'Stop a running CloudWatch Logs Insights query',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              query_id: {
                type: SchemaDefinitionType.STRING,
                description: 'Query ID of the query to stop',
              },
            },
            required: ['query_id'],
          },
        },
      ]),
    });

    // Pricing — read-only pricing access (us-east-1 only)
    const pricingRole = new iam.Role(this, 'PricingRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')],
      inlinePolicies: {
        PricingReadOnly: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['pricing:GetProducts'],
              resources: ['*'],
            }),
          ],
        }),
      },
    });

    const pricingFunction = new lambda.Function(this, 'PricingFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'pricing_tool.lambda_handler',
      code: lambda.Code.fromAsset('lambda'),
      role: pricingRole,
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
    });

    gateway.addLambdaTarget('PricingTarget', {
      gatewayTargetName: 'PricingTool',
      description: 'AWS Pricing API read tool',
      lambdaFunction: pricingFunction,
      toolSchema: ToolSchema.fromInline([
        {
          name: 'pricing_get_products',
          description: 'Get AWS pricing information for a service',
          inputSchema: {
            type: SchemaDefinitionType.OBJECT,
            properties: {
              service_code: {
                type: SchemaDefinitionType.STRING,
                description: 'AWS service code (e.g., AWSLambda)',
              },
              filters: {
                type: SchemaDefinitionType.ARRAY,
                description: 'List of filters to narrow pricing results',
                items: {
                  type: SchemaDefinitionType.OBJECT,
                  properties: {
                    field: { type: SchemaDefinitionType.STRING, description: 'Filter field name' },
                    value: { type: SchemaDefinitionType.STRING, description: 'Filter value' },
                  },
                  required: ['field', 'value'],
                },
              },
            },
            required: ['service_code'],
          },
        },
      ]),
    });

    // Expose outputs for agent runtime env vars
    this.gatewayUrl = gateway.gatewayUrl!;
    this.scope = `${gatewayName}/invoke`;
    this.clientId = userPoolClient.userPoolClientId;
    this.clientSecret = userPoolClient.userPoolClientSecret;
    this.tokenEndpoint = `https://${userPoolDomain.domainName}.auth.${stack.region}.amazoncognito.com/oauth2/token`;

    this.applyNagSuppressions(
      userPool,
      storageRole,
      storageFunction,
      interceptorFunction,
      journalRole,
      journalFunction,
      lambdaDiscoveryRole,
      lambdaDiscoveryFunction,
      cloudwatchMetricsRole,
      cloudwatchMetricsFunction,
      cloudwatchLogsRole,
      cloudwatchLogsFunction,
      pricingRole,
      pricingFunction,
      gateway,
    );
  }

  private applyNagSuppressions(
    userPool: cognito.UserPool,
    storageRole: iam.Role,
    storageFunction: lambda.Function,
    interceptorFunction: lambda.Function,
    journalRole: iam.Role,
    journalFunction: lambda.Function,
    lambdaDiscoveryRole: iam.Role,
    lambdaDiscoveryFunction: lambda.Function,
    cloudwatchMetricsRole: iam.Role,
    cloudwatchMetricsFunction: lambda.Function,
    cloudwatchLogsRole: iam.Role,
    cloudwatchLogsFunction: lambda.Function,
    pricingRole: iam.Role,
    pricingFunction: lambda.Function,
    gateway: AgentCoreGateway,
  ): void {
    NagSuppressions.addResourceSuppressions(
      userPool,
      [
        {
          id: 'AwsSolutions-COG1',
          reason: 'Machine-to-machine OAuth2 client-credentials flow only. No human users authenticate against this pool.',
        },
        {
          id: 'AwsSolutions-COG2',
          reason: 'Machine-to-machine OAuth2 client-credentials flow only. MFA is not applicable.',
        },
        {
          id: 'AwsSolutions-COG3',
          reason: 'Machine-to-machine OAuth2 client-credentials flow only. AdvancedSecurityMode is not applicable.',
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      storageRole,
      [
        {
          id: 'AwsSolutions-IAM4',
          reason: 'AWSLambdaBasicExecutionRole is a well-scoped AWS managed policy for Lambda CloudWatch Logs access.',
          appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'],
        },
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Wildcard S3 actions generated by grantReadWrite(), scoped to the agent data bucket.',
          appliesTo: [
            'Action::s3:Abort*',
            'Action::s3:DeleteObject*',
            'Action::s3:GetBucket*',
            'Action::s3:GetObject*',
            'Action::s3:List*',
          ],
        },
        {
          id: 'AwsSolutions-IAM5',
          reason: 'Wildcard resource ARN for bucket objects generated by grantReadWrite(), scoped to agent data bucket.',
          appliesTo: [{ regex: '/^Resource::.*\\.Arn>\\/\\*$/g' }],
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      [
        storageFunction,
        interceptorFunction,
        journalFunction,
        lambdaDiscoveryFunction,
        cloudwatchMetricsFunction,
        cloudwatchLogsFunction,
        pricingFunction,
      ],
      [
        {
          id: 'AwsSolutions-L1',
          reason: 'Python 3.12 is fully supported by AWS Lambda until October 2028.',
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      interceptorFunction,
      [
        {
          id: 'AwsSolutions-IAM4',
          reason: 'AWSLambdaBasicExecutionRole is a well-scoped AWS managed policy for Lambda CloudWatch Logs access.',
          appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'],
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      journalRole,
      [
        {
          id: 'AwsSolutions-IAM4',
          reason: 'AWSLambdaBasicExecutionRole is a well-scoped AWS managed policy for Lambda CloudWatch Logs access.',
          appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'],
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      [lambdaDiscoveryRole, cloudwatchMetricsRole, cloudwatchLogsRole, pricingRole],
      [
        {
          id: 'AwsSolutions-IAM4',
          reason: 'AWSLambdaBasicExecutionRole is a well-scoped AWS managed policy for Lambda CloudWatch Logs access.',
          appliesTo: ['Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'],
        },
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Wildcard resources required for read-only monitoring operations. Lambda functions, CloudWatch metrics/logs, and Pricing resources are created dynamically. All actions are read-only.',
        },
      ],
      true,
    );

    NagSuppressions.addResourceSuppressions(
      gateway,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Lambda function ARN wildcard (`:*`) added by grantInvoke() for version/alias invocations. Scoped to StorageFunction and JournalFunction ARNs.',
          appliesTo: [{ regex: '/^Resource::.*\\.Arn>:\\*$/g' }],
        },
      ],
      true,
    );
  }
}
