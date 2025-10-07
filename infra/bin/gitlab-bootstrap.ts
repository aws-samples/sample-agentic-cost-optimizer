#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import 'source-map-support/register';

import { GitLabCredentialVendorStack } from '../lib/gitlab-credential-vendor-stack';

const app = new cdk.App();
new GitLabCredentialVendorStack(app, 'AgenticCostOptimizerGitLabCredentialVendor', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },
});
