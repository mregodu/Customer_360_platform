# CI/CD Pipeline

The GitHub Actions pipeline is split into three workflow files:

| Workflow | Purpose | Trigger |
| --- | --- | --- |
| `.github/workflows/ci.yml` | Code quality, unit tests, and repository-level integration checks | Pull request, branch push, manual |
| `.github/workflows/docker.yml` | Docker image build, container healthcheck, and GHCR publishing | Pull request, branch push, tag, manual |
| `.github/workflows/deploy.yml` | Environment-gated deployment automation | Manual or reusable workflow call |

## CI Workflow

The CI workflow runs these gates:

- Ruff linting across `src`, `tests`, and `airflow`.
- mypy type checks for the package and unit tests.
- SQL script termination validation across the `sql` folder.
- YAML and JSON parsing for configs, workflows, and Great Expectations suites.
- Unit tests with the repository pytest configuration and coverage output.
- Integration checks for `configs/test.yaml`, dbt parsing, Airflow DAG imports, and
  optional `tests/integration/test_*.py` modules when they are added.

## Docker Workflow

The Docker workflow builds the repository Dockerfile on pull requests and pushes.
It runs `customer360 healthcheck` inside the image with `configs/test.yaml`.

For non-PR events, the workflow publishes the image to GitHub Container Registry:

```text
ghcr.io/<owner>/customer360-platform:<commit-sha>
```

Branch, tag, and `latest` tags are also emitted by `docker/metadata-action`; `latest`
is published only from `main`.

## Deployment Workflow

Deployment is protected by GitHub environments and can be started manually or called
from another workflow. The Docker workflow automatically calls the deployment workflow
for `dev` when a `main` image is published.

Expected environment secrets:

| Secret | Required | Description |
| --- | --- | --- |
| `CUSTOMER360_DEPLOY_WEBHOOK_URL` | No | External deployment endpoint that receives the image and environment payload. |
| `CUSTOMER360_DEPLOY_WEBHOOK_TOKEN` | No | Bearer token sent to the deployment webhook. |

Expected environment variables:

| Variable | Required | Description |
| --- | --- | --- |
| `CUSTOMER360_HEALTHCHECK_URL` | No | URL called after deployment for smoke testing. |

When the webhook is not configured, the workflow still creates a GitHub deployment
record, verifies the image exists, and exits with a notice. This keeps the pipeline
usable before infrastructure-specific rollout automation is connected.

## Recommended GitHub Environment Rules

- `dev`: automatic deployment from `main`; no manual approval required.
- `staging`: manual dispatch; one reviewer required.
- `prod`: manual dispatch; two reviewers required and deployment branch restricted to
  release tags or `main`.
