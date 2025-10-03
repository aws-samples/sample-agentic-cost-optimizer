# Implementation Plan

- [x] 1. Update agent code to support environment variables and S3 integration
  - Modify src/agents/main.py to read S3_BUCKET_NAME environment variable
  - Add code to print the S3 bucket name when the agent starts
  - Update agent to use Strands framework with environment variable support
  - _Requirements: 2.2, 2.4, 6.3_

- [x] 2. Create Dockerfile for agent containerization
  - Write Dockerfile to package the Strands agent
  - Include Python dependencies from requirements/agents.txt
  - Set up proper entrypoint for agent execution
  - Configure environment variable handling in container
  - _Requirements: 1.2, 2.1_

- [x] 3. Implement CDK infrastructure stack
- [x] 3.1 Create S3 bucket resource
  - Add S3 bucket construct to CDK stack
  - Configure bucket with appropriate permissions
  - Export bucket name for use by other resources
  - _Requirements: 2.1, 4.1, 4.2_

- [x] 3.2 Create ECR repository for agent images
  - Add ECR repository construct to CDK stack
  - Configure repository policies for image management
  - Export repository URI for agent deployment
  - Add DockerImageAsset to automatically build and push Docker image during CDK deployment
  - _Requirements: 1.1, 4.1_

- [x] 3.3 Implement Agent Core runtime resource
  - Add BedrockAgentCore Runtime using L2 construct or L1 CloudFormation resource
  - Configure runtime with automatically built Docker image URI from DockerImageAsset
  - Set up environment variables including S3_BUCKET_NAME
  - Configure IAM role for Agent Core runtime with S3 access
  - _Requirements: 1.1, 1.3, 2.3, 4.3_

- [x] 3.4 Create Lambda function for agent invocation
  - Implement Lambda function code to invoke Agent Core runtime
  - Follow AWS starter toolkit patterns for agent invocation
  - Configure Lambda with appropriate IAM permissions
  - Set up environment variables for runtime ARN reference
  - _Requirements: 3.1, 3.2, 3.4, 5.2_

- [x] 4. Update build and deployment workflow
- [x] 4.1 Add Docker build commands to Makefile
  - Add make target for building agent Docker image locally
  - Integrate with existing uv dependency management
  - Let CDK handle ECR deployment and image pushing automatically
  - _Requirements: 6.1, 6.2, 6.4_

- [x] 4.2 Add CDK deployment commands to Makefile
  - Add make target for CDK bootstrap (if needed)
  - Add make target for CDK deployment
  - Add make target for CDK destroy
  - _Requirements: 6.1, 6.2_

- [x] 5. Deploy and test integration
- [x] 5.1 Deploy CDK stack to create AWS resources
  - Deploy CDK stack with all resources (CDK will handle ECR and image deployment)
  - Get the actual S3 bucket name from CDK outputs
  - Verify all resources are created successfully
  - _Requirements: 1.4, 2.1, 3.1, 4.1_

- [x] 5.2 Test agent locally with real bucket name
  - Set S3_BUCKET_NAME environment variable to actual deployed bucket name
  - Run `make run` to test agent prints bucket name correctly
  - Verify agent works with Strands framework locally
  - _Requirements: 2.4, 6.1_

- [x] 5.3 Test Lambda invocation of agent in cloud
  - Test Lambda invocation of agent through AWS console or CLI
  - Verify S3 bucket name is printed by agent in cloud environment
  - Confirm end-to-end integration works
  - _Requirements: 3.2, 3.3, 5.1, 5.3_