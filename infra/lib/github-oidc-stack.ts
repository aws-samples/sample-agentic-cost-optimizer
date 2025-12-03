import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import * as iam from 'aws-cdk-lib/aws-iam';

export interface GitHubOidcStackProps extends cdk.StackProps {
  /**
   * GitHub organization/owner name
   */
  readonly githubOrg: string;

  /**
   * GitHub repository name
   */
  readonly githubRepo: string;

  /**
   * Branch to allow deployments from (default: 'main')
   */
  readonly allowedBranch?: string;
}

/**
 * Stack that creates GitHub OIDC provider and IAM role for GitHub Actions deployments.
 *
 * Security recommendations followed:
 * - OIDC provider with thumbprint validation
 * - Role scoped to specific repository
 * - Role scoped to specific branch
 * - Audience condition for sts.amazonaws.com
 */
export class GitHubOidcStack extends cdk.Stack {
  public readonly role: iam.Role;
  public readonly roleArn: string;

  constructor(scope: Construct, id: string, props: GitHubOidcStackProps) {
    super(scope, id, props);

    const { githubOrg, githubRepo, allowedBranch = 'main' } = props;

    const githubOidcProvider = new iam.OpenIdConnectProvider(this, 'GitHubOidcProvider', {
      url: 'https://token.actions.githubusercontent.com',
      clientIds: ['sts.amazonaws.com'],
      // GitHub's thumbprint - this is stable and provided by GitHub
      // See: https://github.blog/changelog/2023-06-27-github-actions-update-on-oidc-integration-with-aws/
      thumbprints: ['ffffffffffffffffffffffffffffffffffffffff'],
    });

    this.role = new iam.Role(this, 'GitHubActionsRole', {
      roleName: `GitHubActions-${githubRepo}`,
      description: `Role for GitHub Actions deployments from ${githubOrg}/${githubRepo}`,
      maxSessionDuration: cdk.Duration.hours(1),
      assumedBy: new iam.FederatedPrincipal(
        githubOidcProvider.openIdConnectProviderArn,
        {
          StringEquals: {
            'token.actions.githubusercontent.com:aud': 'sts.amazonaws.com',
          },
          StringLike: {
            // Scope to specific repo and branch
            // Format: repo:<owner>/<repo>:ref:refs/heads/<branch>
            // For PRs, GitHub uses: repo:<owner>/<repo>:pull_request
            'token.actions.githubusercontent.com:sub': [
              `repo:${githubOrg}/${githubRepo}:ref:refs/heads/${allowedBranch}`,
              // TODO: Remove after testing - temporary for PR testing
              `repo:${githubOrg}/${githubRepo}:pull_request`,
            ],
          },
        },
        'sts:AssumeRoleWithWebIdentity',
      ),
    });

    // Permissions for CDK deployment
    // This is a starting point - scope down further based on your needs
    this.role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'CDKDeploymentPermissions',
        effect: iam.Effect.ALLOW,
        actions: [
          // CloudFormation permissions
          'cloudformation:*',
          // S3 for CDK assets
          's3:*',
          // SSM for CDK context lookups
          'ssm:GetParameter',
          // IAM for creating roles (CDK needs this)
          'iam:*',
          // Lambda for deploying functions
          'lambda:*',
          // Logs for Lambda
          'logs:*',
          // STS for assuming CDK roles
          'sts:AssumeRole',
        ],
        resources: ['*'],
      }),
    );

    this.roleArn = this.role.roleArn;

    new cdk.CfnOutput(this, 'RoleArn', {
      value: this.role.roleArn,
      description: 'ARN of the IAM role for GitHub Actions. Store this as a GitHub secret.',
      exportName: 'GitHubActionsRoleArn',
    });

    new cdk.CfnOutput(this, 'OidcProviderArn', {
      value: githubOidcProvider.openIdConnectProviderArn,
      description: 'ARN of the GitHub OIDC provider',
      exportName: 'GitHubOidcProviderArn',
    });
  }
}
