#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';

import { GitHubOidcStack } from '../lib/github-oidc-stack';

/**
 * GitHub OIDC Setup for GitHub Actions deployments.
 *
 * This is a one-time setup (similar to CDK bootstrap) that creates:
 * 1. GitHub OIDC Identity Provider in AWS
 * 2. IAM Role that GitHub Actions can assume
 *
 * Usage:
 *   npx cdk deploy --app "npx ts-node bin/github-oidc.ts"
 *
 * After deployment:
 * 1. Copy the RoleArn from the stack outputs
 * 2. Add it as a GitHub secret named AWS_ROLE_ARN
 */
const app = new cdk.App();

new GitHubOidcStack(app, 'GitHubOidcStack', {
  description: 'GitHub OIDC provider and IAM role for GitHub Actions deployments',
  githubOrg: 'aws-samples',
  githubRepo: 'sample-agentic-cost-optimizer',
  environment: 'dev',
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
