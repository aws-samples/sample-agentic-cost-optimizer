import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';

import * as iam from 'aws-cdk-lib/aws-iam';

export class GitLabCredentialVendorStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Safety check - only deploy to the intended account
    if (this.account !== '249634239082') {
      throw new Error(`Bootstrap can only be deployed to account 249634239082, current: ${this.account}`);
    }

    // GitLab CI/CD Role for AWS Credential Vendor
    const gitlabRole = new iam.Role(this, 'GitLabCIRole', {
      roleName: 'GitLabCI-AgenticCostOptimizer',
      assumedBy: new iam.ArnPrincipal('arn:aws:iam::979517299116:role/gitlab-runners-prod'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('PowerUserAccess')],
    });

    new cdk.CfnOutput(this, 'GitLabRoleArn', {
      value: gitlabRole.roleArn,
      description: 'GitLab CI/CD Role ARN',
    });
  }
}
