import * as cdk from 'aws-cdk-lib';
import { NagSuppressions } from 'cdk-nag';
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
   * GitHub environment name for OIDC subject claim (e.g., 'dev', 'prod')
   */
  readonly environment: string;
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

    const { githubOrg, githubRepo, environment } = props;

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
            // With GitHub Environments, subject format is: repo:<owner>/<repo>:environment:<name>
            'token.actions.githubusercontent.com:sub': `repo:${githubOrg}/${githubRepo}:environment:${environment}`,
          },
        },
        'sts:AssumeRoleWithWebIdentity',
      ),
    });

    // CDK v2 bootstrap roles have all necessary permissions for deployment:
    // - deploy-role: CloudFormation operations
    // - file-publishing-role: S3 asset uploads
    // - image-publishing-role: ECR image publishing
    // - lookup-role: SSM lookups and context queries
    this.role.addToPolicy(
      new iam.PolicyStatement({
        sid: 'AssumeBootstrapRoles',
        effect: iam.Effect.ALLOW,
        actions: ['sts:AssumeRole'],
        resources: [
          `arn:aws:iam::${cdk.Aws.ACCOUNT_ID}:role/cdk-*-deploy-role-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
          `arn:aws:iam::${cdk.Aws.ACCOUNT_ID}:role/cdk-*-file-publishing-role-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
          `arn:aws:iam::${cdk.Aws.ACCOUNT_ID}:role/cdk-*-image-publishing-role-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
          `arn:aws:iam::${cdk.Aws.ACCOUNT_ID}:role/cdk-*-lookup-role-${cdk.Aws.ACCOUNT_ID}-${cdk.Aws.REGION}`,
        ],
      }),
    );

    this.roleArn = this.role.roleArn;

    new cdk.CfnOutput(this, 'RoleArn', {
      value: this.role.roleArn,
      description: 'ARN of the IAM role for GitHub Actions. Store this as a GitHub secret.',
    });

    new cdk.CfnOutput(this, 'OidcProviderArn', {
      value: githubOidcProvider.openIdConnectProviderArn,
      description: 'ARN of the GitHub OIDC provider',
    });

    // CDK Nag suppressions
    // NOTE: This is a sample for demonstration purposes. Review and adjust for production use.
    NagSuppressions.addResourceSuppressions(
      this.role,
      [
        {
          id: 'AwsSolutions-IAM5',
          reason:
            'Sample code: Wildcard in CDK bootstrap role names is required because the qualifier varies per bootstrap. Roles are scoped to specific account/region. See: https://docs.aws.amazon.com/cdk/v2/guide/bootstrapping.html',
          appliesTo: [
            'Resource::arn:aws:iam::<AWS::AccountId>:role/cdk-*-deploy-role-<AWS::AccountId>-<AWS::Region>',
            'Resource::arn:aws:iam::<AWS::AccountId>:role/cdk-*-file-publishing-role-<AWS::AccountId>-<AWS::Region>',
            'Resource::arn:aws:iam::<AWS::AccountId>:role/cdk-*-image-publishing-role-<AWS::AccountId>-<AWS::Region>',
            'Resource::arn:aws:iam::<AWS::AccountId>:role/cdk-*-lookup-role-<AWS::AccountId>-<AWS::Region>',
          ],
        },
      ],
      true,
    );
  }
}
