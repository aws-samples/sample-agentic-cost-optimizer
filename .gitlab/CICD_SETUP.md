# CI/CD Setup Guide

## Prerequisites

1. AWS CLI configured with appropriate permissions
2. Node.js and npm installed

## One-time Setup

Run the account bootstrap to set up GitLab CI/CD role:

```bash
make account-bootstrap
```

This creates:
- GitLab CI/CD IAM role with PowerUser permissions
- OIDC trust relationship for your GitLab project

## Pipeline Behavior

- Automatically deploys to AWS when code is merged to `main` branch
- Uses AWS credential vendor for secure authentication
- Deploys the main CDK stack (not the bootstrap stack)

## Manual Deployment

```bash
make cdk-deploy
```