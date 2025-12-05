import { App } from 'aws-cdk-lib';
import { describe, expect, it } from 'vitest';

import { Template } from 'aws-cdk-lib/assertions';

import { GitHubOidcStack } from '../lib/github-oidc-stack';

function createOidcTestStack(environment: string) {
  const app = new App();
  const stack = new GitHubOidcStack(app, 'TestOidcStack', {
    githubOrg: 'test-org',
    githubRepo: 'test-repo',
    environment,
  });
  const template = Template.fromStack(stack);
  return { app, stack, template };
}

describe('GitHubOidcStack', () => {
  describe('OIDC Provider', () => {
    it('should create GitHub OIDC provider with correct URL', () => {
      const { template } = createOidcTestStack('staging');

      template.hasResourceProperties('Custom::AWSCDKOpenIdConnectProvider', {
        Url: 'https://token.actions.githubusercontent.com',
        ClientIDList: ['sts.amazonaws.com'],
      });
    });
  });

  describe('IAM Role', () => {
    it('should create role with correct name pattern', () => {
      const { template } = createOidcTestStack('staging');

      template.hasResourceProperties('AWS::IAM::Role', {
        RoleName: 'GitHubActions-test-repo',
        MaxSessionDuration: 3600,
      });
    });

    it('should scope trust policy to specific repo and environment', () => {
      const { template } = createOidcTestStack('staging');

      const roles = template.findResources('AWS::IAM::Role', {
        Properties: {
          RoleName: 'GitHubActions-test-repo',
        },
      });

      const role = Object.values(roles)[0] as {
        Properties: {
          AssumeRolePolicyDocument: {
            Statement: Array<{
              Condition: {
                StringEquals: Record<string, string>;
                StringLike: Record<string, string>;
              };
            }>;
          };
        };
      };

      const statement = role.Properties.AssumeRolePolicyDocument.Statement[0];
      expect(statement.Condition.StringEquals['token.actions.githubusercontent.com:aud']).toBe('sts.amazonaws.com');
      expect(statement.Condition.StringLike['token.actions.githubusercontent.com:sub']).toBe('repo:test-org/test-repo:environment:staging');
    });

    it('should use prod environment in trust policy when specified', () => {
      const { template } = createOidcTestStack('prod');

      const roles = template.findResources('AWS::IAM::Role', {
        Properties: {
          RoleName: 'GitHubActions-test-repo',
        },
      });

      const role = Object.values(roles)[0] as {
        Properties: {
          AssumeRolePolicyDocument: {
            Statement: Array<{
              Condition: {
                StringLike: Record<string, string>;
              };
            }>;
          };
        };
      };

      const statement = role.Properties.AssumeRolePolicyDocument.Statement[0];
      expect(statement.Condition.StringLike['token.actions.githubusercontent.com:sub']).toBe('repo:test-org/test-repo:environment:prod');
    });
  });

  describe('IAM Policy', () => {
    it('should only allow sts:AssumeRole action', () => {
      const { template } = createOidcTestStack('staging');

      const policies = template.findResources('AWS::IAM::Policy');
      const policy = Object.values(policies)[0] as {
        Properties: {
          PolicyDocument: {
            Statement: Array<{
              Action: string;
              Sid: string;
            }>;
          };
        };
      };

      const statement = policy.Properties.PolicyDocument.Statement.find((s) => s.Sid === 'AssumeBootstrapRoles');
      expect(statement).toBeDefined();
      expect(statement!.Action).toBe('sts:AssumeRole');
    });

    it('should scope to CDK bootstrap roles only', () => {
      const { template } = createOidcTestStack('staging');

      const policies = template.findResources('AWS::IAM::Policy');
      const policy = Object.values(policies)[0] as {
        Properties: {
          PolicyDocument: {
            Statement: Array<{
              Resource: unknown[];
              Sid: string;
            }>;
          };
        };
      };

      const statement = policy.Properties.PolicyDocument.Statement.find((s) => s.Sid === 'AssumeBootstrapRoles');
      const resources = JSON.stringify(statement!.Resource);

      expect(resources).toContain('cdk-*-deploy-role');
      expect(resources).toContain('cdk-*-file-publishing-role');
      expect(resources).toContain('cdk-*-image-publishing-role');
      expect(resources).toContain('cdk-*-lookup-role');
    });
  });

  describe('Stack Outputs', () => {
    it('should output RoleArn', () => {
      const { template } = createOidcTestStack('staging');

      template.hasOutput('RoleArn', {
        Description: 'ARN of the IAM role for GitHub Actions. Store this as a GitHub secret.',
      });
    });

    it('should output OidcProviderArn', () => {
      const { template } = createOidcTestStack('staging');

      template.hasOutput('OidcProviderArn', {
        Description: 'ARN of the GitHub OIDC provider',
      });
    });
  });
});
