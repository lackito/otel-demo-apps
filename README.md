# otel-demo-apps
OpenTelemetry Demo Applications

Application source code for the OpenTelemetry Demo platform.

This repository contains the application services, CI pipelines, Dockerfiles, and supporting artifacts used by the platform.

## Repository Structure

```
apps/
.github/workflows/
```

## Recommendation CI/CD

`.github/workflows/recommendation-release.yml` runs for changes to the
recommendation service merged to `main` (or when manually dispatched). It:

1. assumes an AWS IAM role through GitHub OIDC;
2. builds `apps/recommendation` and pushes a commit-SHA-tagged image to the
   Terraform-managed `recommendation` ECR repository in `us-east-1`;
3. updates the recommendation tag in `otel-demo-gitops`; and
4. lets the existing Argo CD application synchronize the resulting desired state.

Before enabling the workflow, add these repository secrets to `otel-demo-apps`:

| Secret | Purpose |
| --- | --- |
| `AWS_ROLE_TO_ASSUME` | ARN of the IAM role trusted by GitHub Actions OIDC and permitted to push to the `recommendation` ECR repository. |
| `GITOPS_REPOSITORY_TOKEN` | Fine-grained GitHub token with **Contents: Read and write** access to `lackito/otel-demo-gitops`. |

The IAM role trust policy must restrict the GitHub OIDC subject to
`repo:lackito/otel-demo-apps:ref:refs/heads/main`. The role needs only ECR push
permissions for the `recommendation` repository plus `ecr:GetAuthorizationToken`.

The release workflow intentionally updates the GitOps repository rather than
deploying to Kubernetes directly. Argo CD remains the sole owner of workloads.

CI/CD test
