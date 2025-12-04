# CI/CD Pipeline

## Environments

| Environment | Purpose | OIDC Setup | Deployed via |
|-------------|---------|------------|--------------|
| `dev` | Local development | No | Manual (`npm run deploy`) |
| `staging` | Pre-prod testing, integ tests | Yes | CI/CD on merge to main |
| `prod` | Production | Yes | CI/CD after staging tests pass |

## Prerequisites (One-time setup per AWS account)

1. Bootstrap CDK in each account: `cdk bootstrap`
2. Deploy OIDC stack for CI/CD environments:
   - `ENVIRONMENT=staging npm run deploy:oidc --prefix infra` (staging account)
   - `ENVIRONMENT=prod npm run deploy:oidc --prefix infra` (prod account)
3. Create GitHub environments (`staging`, `prod`) with `AWS_ROLE_ARN` secret from each OIDC stack output
4. Configure environment protection rules (limit deployments to `main` branch only)
5. Configure branch protection rules on `main` (require PR reviews, status checks)

## Pipeline Flow

### 1. PR Created/Updated

- Runs: `test-python`, `test-typescript`, `test-cdk-nag`
- No deployment, no AWS credentials needed

### 2. PR Merged to Main

- Unit tests run again
- `deploy-staging` → deploys to staging account (GitHub environment: `staging`)
- `test-integration` → runs integration/eval tests against staging
- `deploy-prod` → deploys to prod account (GitHub environment: `prod`)

## GitHub Environments

Two environments (`staging`, `prod`) provide isolation with separate secrets, protection rules, and deployment history per environment.

## Rollback Strategy

- **Option 1:** Create a revert PR (`git revert <bad-commit>`) → merge to main → triggers full pipeline
- **Option 2:** Re-run previous successful workflow from GitHub Actions UI (runs retained for 90 days by default)

## Security

- **No long-lived credentials:** OIDC authentication eliminates stored AWS access keys
- **Environment isolation:** Each AWS account has its own OIDC role scoped to its GitHub environment
- **Least privilege:** GitHub Actions role can only assume CDK bootstrap roles, not direct resource access
- **Supply chain protection:** All GitHub Actions are pinned to SHA hashes
- **Branch protection:** Deployments only trigger on push to `main` (requires PR merge)
- **Concurrency control:** Prevents parallel deployments to the same environment
