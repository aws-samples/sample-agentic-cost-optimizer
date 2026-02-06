# CI/CD Pipeline

## Environments

| Environment | Purpose | OIDC Setup | Deployed via |
|-------------|---------|------------|--------------|
| `dev` | Local development | No | Manual (`make cdk-deploy`) |
| `staging` | Pre-prod testing, integ tests | Yes | CI/CD on merge to main |
| `prod` | Production | Yes | CI/CD after staging tests pass |

## Environment-Based Features

Features are automatically configured based on the `ENVIRONMENT` variable:

| Feature | dev | staging | prod |
|---------|-----|---------|------|
| Scheduled Trigger (6am UTC) | ❌ | ❌ | ✅ |
| Manual Trigger | ✅ | ✅ | ❌ |
| Online Evaluations | ❌ | ❌ | ✅ |

Override defaults with environment variables:
- `ENABLE_EVALS=true` - Enable Online Evaluations in any environment
- `ENABLE_SCHEDULED_TRIGGER=true` - Enable scheduled trigger in any environment

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

Runs test jobs (no AWS credentials needed):
- `test-python` - Python unit tests with coverage
- `test-typescript` - TypeScript/CDK unit tests
- `test-cdk-nag` - CDK security checks via cdk-nag

### 2. PR Merged to Main

Deployments only trigger when relevant files change:
- `src/**`, `infra/**`, `tests/**`, `evals/**`, `scripts/**`
- `pyproject.toml`, `uv.lock`
- `.github/workflows/ci.yml`

Pipeline sequence:
1. Unit tests run again (`test-python`, `test-typescript`, `test-cdk-nag`)
2. `deploy-staging` → deploys with `ENVIRONMENT=staging`
3. `deploy-prod` → deploys with `ENVIRONMENT=prod`

Changes to docs, reports, or other non-deployment files skip the deployment jobs.

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

### Fork PR Protection

Fork PRs require manual approval before workflows run. This is controlled by a repo-level setting, not the workflow file itself.

**Required setting:** Settings → Actions → General → "Require approval for all external contributors"

This ensures:
- Every push from a fork requires maintainer approval
- Every new PR from a fork requires approval
- Malicious workflow modifications in forks cannot execute without review
- Maintainers can inspect the diff (including `.github/workflows/`) before approving
