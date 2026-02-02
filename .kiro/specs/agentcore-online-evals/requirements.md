# Requirements Document

## Introduction

This feature adds AgentCore Online Evaluations to the agentic-cost-optimizer project using a CDK Custom Resource. Since the CDK L2 construct (`@aws-cdk/aws-bedrock-agentcore-alpha`) is not yet published to npm, this is a temporary implementation that calls the boto3 API directly via a Lambda-backed Custom Resource. The implementation will be replaced by the L2 construct once it becomes available.

## Glossary

- **Evals_Construct**: The CDK construct that creates and manages the Online Evaluation configuration via AwsCustomResource
- **AwsCustomResource**: The CDK construct from `aws-cdk-lib/custom-resources` that handles CloudFormation Custom Resource lifecycle and SDK calls automatically
- **Execution_Role**: The IAM role assumed by the Bedrock AgentCore service to perform evaluations
- **Online_Evaluation_Config**: The Bedrock AgentCore configuration that defines which evaluators to run and how to sample agent traces
- **Evaluator**: A built-in assessment module that evaluates specific aspects of agent performance (e.g., CORRECTNESS, HELPFULNESS)
- **Data_Source_Config**: The CloudWatch Logs configuration specifying where to read agent traces from, containing `logGroupNames` and `serviceNames` derived from the AgentCore Runtime
- **Runtime_Id**: The unique identifier of the AgentCore Runtime (e.g., `agentRuntime_dev_v2-Fgmi5R78OC`)
- **Runtime_Name**: The name of the AgentCore Runtime (e.g., `agentRuntime_dev_v2`)
- **Endpoint_Name**: The name of the runtime endpoint, defaults to `DEFAULT`
- **Sampling_Percentage**: The percentage of agent traces to evaluate (0.01-100)
- **Session_Timeout**: Minutes of inactivity after which an agent session is considered complete

## Requirements

### Requirement 1: Deployment Control

**User Story:** As a developer, I want to control when Online Evaluations are deployed, so that I can enable them only in production by default while allowing override for testing.

#### Acceptance Criteria

1. THE Infra_Stack SHALL accept an `enableEvals` boolean property
2. WHEN `enableEvals` is not specified, THE Infra_Stack SHALL default to `true` only when `environment === 'prod'`
3. WHEN `enableEvals` is `true`, THE Infra_Stack SHALL create the Evals_Construct
4. WHEN `enableEvals` is `false`, THE Infra_Stack SHALL NOT create the Evals_Construct
5. THE bin/infra.ts SHALL pass `enableEvals` to InfraStack based on environment with override capability

### Requirement 2: Configuration Constants

**User Story:** As a developer, I want evaluation configuration centralized in a constants file, so that I can easily modify settings without changing construct code.

#### Acceptance Criteria

1. THE evals-config.ts SHALL define a `samplingPercentage` constant with default value `100`
2. THE evals-config.ts SHALL define a `sessionTimeoutMinutes` constant with default value `5`
3. THE evals-config.ts SHALL define a `configNamePattern` function that returns `cost_optimizer_eval_{environment}`
4. THE evals-config.ts SHALL define an array of 10 built-in evaluator identifiers:
   - `Builtin.ToolSelectionAccuracy`
   - `Builtin.ToolParameterAccuracy`
   - `Builtin.Correctness`
   - `Builtin.Helpfulness`
   - `Builtin.Conciseness`
   - `Builtin.InstructionFollowing`
   - `Builtin.ResponseRelevance`
   - `Builtin.Coherence`
   - `Builtin.Faithfulness`
   - `Builtin.GoalSuccessRate`
5. THE evals-config.ts SHALL export all constants for use by the Evals_Construct

### Requirement 3: Evals Construct

**User Story:** As a developer, I want a CDK construct that creates Online Evaluation configurations, so that I can deploy evaluations as infrastructure-as-code.

#### Acceptance Criteria

1. THE Evals_Construct SHALL accept the Agent construct as a required property to derive runtime details
2. THE Evals_Construct SHALL derive the log group name using pattern `/aws/bedrock-agentcore/runtimes/{runtimeId}-{endpointName}` where `endpointName` defaults to `DEFAULT`
3. THE Evals_Construct SHALL derive the service name using pattern `{runtimeName}.{endpointName}` where `endpointName` defaults to `DEFAULT`
4. THE Evals_Construct SHALL create an Execution_Role with the required IAM permissions
5. THE Evals_Construct SHALL create an AwsCustomResource to manage the evaluation config via SDK calls
6. THE AwsCustomResource SHALL call `CreateOnlineEvaluationConfig` on create
7. THE AwsCustomResource SHALL call `UpdateOnlineEvaluationConfig` on update
8. THE AwsCustomResource SHALL call `DeleteOnlineEvaluationConfig` on delete
9. THE Evals_Construct SHALL output the evaluation config ID and ARN as CloudFormation outputs

### Requirement 4: Execution Role Permissions

**User Story:** As a security-conscious developer, I want the execution role to have minimal required permissions, so that the evaluation service operates with least privilege.

#### Acceptance Criteria

1. THE Execution_Role SHALL have a trust policy allowing `bedrock-agentcore.amazonaws.com` to assume it
2. THE Execution_Role trust policy SHALL include conditions for `aws:SourceAccount` and `aws:ResourceAccount`
3. THE Execution_Role SHALL have CloudWatch Logs read permissions: `logs:DescribeLogGroups`, `logs:GetQueryResults`, `logs:StartQuery`
4. THE Execution_Role SHALL have CloudWatch Logs write permissions for `/aws/bedrock-agentcore/evaluations/*`: `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`
5. THE Execution_Role SHALL have CloudWatch index policy permissions for `aws/spans`: `logs:DescribeIndexPolicies`, `logs:PutIndexPolicy`
6. THE Execution_Role SHALL have Bedrock model invocation permissions: `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream`

### Requirement 5: AwsCustomResource Permissions

**User Story:** As a developer, I want the AwsCustomResource to have the correct IAM permissions, so that it can manage evaluation configs via SDK calls.

#### Acceptance Criteria

1. THE AwsCustomResource policy SHALL have permissions to manage evaluation configs: `bedrock-agentcore:CreateOnlineEvaluationConfig`, `bedrock-agentcore:GetOnlineEvaluationConfig`, `bedrock-agentcore:UpdateOnlineEvaluationConfig`, `bedrock-agentcore:DeleteOnlineEvaluationConfig`, `bedrock-agentcore:ListOnlineEvaluationConfigs`
2. THE AwsCustomResource policy SHALL have `iam:PassRole` permission for the Execution_Role
3. THE AwsCustomResource policy SHALL have CloudWatch index policy permissions: `logs:DescribeIndexPolicies`, `logs:PutIndexPolicy`, `logs:CreateLogGroup`

### Requirement 6: Unit Tests

**User Story:** As a developer, I want comprehensive unit tests, so that I can verify the construct behaves correctly.

#### Acceptance Criteria

1. THE test suite SHALL verify the Evals_Construct creates an AwsCustomResource when enabled
2. THE test suite SHALL verify the Evals_Construct does NOT create resources when disabled
3. THE test suite SHALL verify the Execution_Role has the correct trust policy
4. THE test suite SHALL verify the Execution_Role has CloudWatch Logs read permissions
5. THE test suite SHALL verify the Execution_Role has CloudWatch Logs write permissions
6. THE test suite SHALL verify the Execution_Role has Bedrock model invocation permissions
7. THE test suite SHALL follow existing test patterns using vitest
