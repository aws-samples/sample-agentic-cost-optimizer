#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { AwsSolutionsChecks } from 'cdk-nag';

import { GitHubOidcStack } from '../lib/github-oidc-stack';

/**
 * GitHub OIDC Setup for GitHub Actions deployments.
 *
 * This is a one-time setup (similar to CDK bootstrap) that creates:
 * 1. GitHub OIDC Identity Provider in AWS
 * 2. IAM Role that GitHub Actions can assume
 *
 * Usage:
 *   ENVIRONMENT=staging npm run deploy:oidc --prefix infra
 *   ENVIRONMENT=prod npm run deploy:oidc --prefix infra
 *
 *
 * After deployment:
 * 1. Copy the RoleArn from the stack outputs
 * 2. Add it as a GitHub secret named AWS_ROLE_ARN in the corresponding GitHub environment
 */

const VALID_ENVIRONMENTS = ['staging', 'prod'];
const environment = process.env.ENVIRONMENT;

if (!environment || !VALID_ENVIRONMENTS.includes(environment)) {
  console.error('\nENVIRONMENT must be "staging" or "prod".\n');
  console.error('Usage: ENVIRONMENT=staging npm run deploy:oidc --prefix infra');
  console.error('       ENVIRONMENT=prod npm run deploy:oidc --prefix infra\n');
  process.exit(1);
}

const app = new cdk.App();

new GitHubOidcStack(app, `GitHubOidcStack-${environment}`, {
  description: `GitHub OIDC provider and IAM role for GitHub Actions deployments (${environment})`,
  githubOrg: 'aws-samples',
  githubRepo: 'sample-agentic-cost-optimizer',
  environment,
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});

cdk.Aspects.of(app).add(new AwsSolutionsChecks({ verbose: true }));
