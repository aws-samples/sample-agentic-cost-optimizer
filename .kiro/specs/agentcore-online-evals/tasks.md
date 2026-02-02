# Implementation Plan: AgentCore Online Evaluations

## Overview

This implementation plan follows a proper feature development lifecycle:
1. Create code in logical chunks
2. Test each chunk when possible
3. Commit after each logical phase
4. Deploy to dev when ready

The implementation uses TypeScript for CDK constructs and vitest for testing. No Python Lambda code is needed since we use `AwsCustomResource`.

## Tasks

- [-] 1. Create configuration constants
  - [x] 1.1 Create `constants/evals-config.ts` with evaluation configuration
    - Define `samplingPercentage` (100)
    - Define `sessionTimeoutMinutes` (5)
    - Define `evaluators` array with 10 built-in evaluators
    - Define `defaultEndpointName` ('DEFAULT')
    - Export `getEvalsConfigName(environment)` function
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 1.2 Write unit tests for evals-config
    - Test `getEvalsConfigName` returns correct pattern
    - Test constants have expected values
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 2. Checkpoint - Run tests and commit
  - Run `make test` to verify config tests pass
  - Commit: "feat(evals): add evaluation configuration constants"

- [x] 3. Create Evals construct
  - [x] 3.1 Create `lib/evals.ts` with Evals construct class
    - Define `EvalsProps` interface accepting Agent and environment
    - Create execution role with trust policy for `bedrock-agentcore.amazonaws.com`
    - Add CloudWatch Logs read permissions to execution role
    - Add CloudWatch Logs write permissions for `/aws/bedrock-agentcore/evaluations/*`
    - Add CloudWatch index policy permissions for `aws/spans`
    - Add Bedrock model invocation permissions
    - _Requirements: 3.1, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x] 3.2 Add AwsCustomResource to Evals construct
    - Derive log group name from Agent runtime: `/aws/bedrock-agentcore/runtimes/{runtimeId}-DEFAULT`
    - Derive service name from Agent runtime: `{runtimeName}.DEFAULT`
    - Create AwsCustomResource with onCreate/onUpdate/onDelete handlers
    - Add policy for bedrock-agentcore admin permissions
    - Add policy for iam:PassRole
    - Add policy for CloudWatch index permissions
    - Export configId and configArn from custom resource response
    - _Requirements: 3.2, 3.3, 3.5, 3.6, 3.7, 3.8, 3.9, 5.1, 5.2, 5.3_

  - [x] 3.3 Add CDK Nag suppressions to Evals construct
    - Suppress wildcard warnings with appropriate justifications
    - Follow existing patterns from Agent construct
    - _Requirements: 3.4_

  - [x] 3.4 Write unit tests for Evals construct
    - Test execution role has correct trust policy
    - Test execution role has CloudWatch Logs read permissions
    - Test execution role has CloudWatch Logs write permissions
    - Test execution role has CloudWatch index policy permissions
    - Test execution role has Bedrock model permissions
    - Test AwsCustomResource is created with correct service/action
    - Test AwsCustomResource policy has admin permissions
    - Test AwsCustomResource policy has PassRole permission
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 5.1, 5.2, 5.3, 6.1, 6.3, 6.4, 6.5, 6.6_

- [-] 4. Checkpoint - Run tests and commit
  - Run `make test` to verify Evals construct tests pass
  - Commit: "feat(evals): add Evals construct with AwsCustomResource"

- [ ] 5. Integrate Evals into InfraStack
  - [ ] 5.1 Update `lib/infra-stack.ts` to add enableEvals prop
    - Add `enableEvals?: boolean` to InfraStackProps
    - Conditionally create Evals construct when enableEvals is true
    - Add CfnOutputs for evaluation config ID and ARN
    - _Requirements: 1.1, 1.3, 1.4_

  - [ ] 5.2 Update `bin/infra.ts` to pass enableEvals
    - Default enableEvals to `environment === 'prod'`
    - Allow override via environment variable or context
    - _Requirements: 1.2, 1.5_

  - [ ]* 5.3 Write unit tests for conditional Evals creation
    - Test Evals construct is created when enableEvals=true
    - Test Evals construct is NOT created when enableEvals=false
    - Test default enableEvals behavior based on environment
    - _Requirements: 1.2, 1.3, 1.4, 6.1, 6.2_

- [ ] 6. Checkpoint - Run all tests and commit
  - Run `make test` to verify all tests pass
  - Run `make check` to verify code style
  - Commit: "feat(evals): integrate Evals construct into InfraStack"

- [ ] 7. Final verification
  - [ ] 7.1 Run CDK synth to verify template generation
    - Run `npx cdk synth` with enableEvals=true
    - Verify Custom Resource is in template
    - Verify IAM roles and policies are correct
    - _Requirements: All_

  - [ ] 7.2 Update README if needed
    - Document enableEvals prop
    - Document how to enable/disable evaluations
    - _Requirements: Documentation_

- [ ] 8. Deploy to dev environment
  - Run `npx cdk deploy` with enableEvals=true in dev
  - Verify evaluation config is created in AWS console
  - Verify no deployment errors

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each checkpoint includes running tests and committing
- The implementation follows existing patterns from the Agent construct
- Property tests use fast-check library (install if not present)
- All tests use vitest following existing project patterns
