# otel-demo-apps
OpenTelemetry Demo Applications

Application source code for the OpenTelemetry Demo platform.

This repository contains the application services, CI pipelines, Dockerfiles, and supporting artifacts used by the platform.

See the
[AWS and local project walkthrough](https://github.com/lackito/otel-demo-local/blob/main/docs/PROJECT_WALKTHROUGH.md)
for the shared source-to-Argo CD delivery model.

## Repository Structure

```
apps/
.github/workflows/
```

## Environment boundary

This repository contains reusable application source and two
environment-specific release workflows.

| Application branch | Release target |
| --- | --- |
| `local` | GHCR, `otel-demo-gitops-local`, and the local kind cluster |
| `main` | Amazon ECR, `otel-demo-gitops`, and Amazon EKS |

For local experimentation, commit changes on a local development branch so
the image receives a new commit-based tag. The branch does not need to be
pushed for direct kind loading. Pushing Recommendation changes to the `local`
branch invokes local CI. Merging those validated changes into `main` invokes
the AWS release workflow.

## Local Recommendation CI/CD

`.github/workflows/recommendation-local-release.yml` runs when Recommendation
code is pushed to the `local` branch. It:

1. uses the triggering commit SHA as the immutable image tag;
2. builds `apps/recommendation` for `linux/arm64`;
3. publishes the image to
   `ghcr.io/lackito/otel-demo-local-recommendation`;
4. updates `applications/otel-demo/values.yaml` in `otel-demo-gitops-local`;
5. lets local Argo CD deploy the generated desired-state commit to kind.

Add `LOCAL_GITOPS_REPOSITORY_TOKEN` to the `otel-demo-apps` repository secrets.
It must be a fine-grained token with **Contents: Read and write** access to
`lackito/otel-demo-gitops-local`. If the token predates the GitOps repository,
edit its repository access and explicitly add `otel-demo-gitops-local` before
running the workflow.

Add `GHCR_PAT` as a second repository secret. It must be a personal access
token (classic) owned by `lackito` with `write:packages` scope. It is used only
to publish the local image to GHCR.

The local GHCR package must be public so kind can pull it without registry
credentials. The local workflow does not use AWS credentials, ECR, or
`otel-demo-gitops`.

### Validate a local release

After pushing Recommendation code to the `local` branch, validate every CI
handoff instead of relying only on the final application response.

1. Open **otel-demo-apps → Actions → Release recommendation service to
   local Kubernetes** and select the run for the pushed commit.
2. Confirm the run shows `local` as its branch and the expected commit SHA.
3. Inspect these successful log steps:
   - **Build and publish arm64 image** pushed
     `ghcr.io/lackito/otel-demo-local-recommendation:<commit-sha>`;
   - **Verify anonymous image access** confirmed kind can pull it;
   - **Update local desired image** changed only the Recommendation repository
     and tag;
   - **Commit and push local desired state** created the generated GitOps
     commit in `otel-demo-gitops-local`.
4. Open the GHCR package and confirm that the full application commit SHA is
   present as an image tag.

Record the triggering application SHA locally with:

```bash
git switch local
git rev-parse HEAD
```

The same SHA should appear in the workflow logs, GHCR image tag, generated
`otel-demo-gitops-local` values commit, and running Kubernetes Deployment.

## AWS Recommendation CI/CD

`.github/workflows/recommendation-release.yml` runs for changes to the
recommendation service merged to `main` (or when manually dispatched). It:

1. assumes an AWS IAM role through GitHub OIDC;
2. builds `apps/recommendation` and pushes a commit-SHA-tagged image to the
   Terraform-managed `recommendation` ECR repository in `us-east-1`;
3. updates the recommendation tag in `otel-demo-gitops`; and
4. lets the existing Argo CD application synchronize the resulting desired state.

The non-sensitive IAM role ARN is configured directly in the AWS-specific
workflow so the job cannot silently target a stale role from a repository
secret. Add this repository secret to `otel-demo-apps`:

| Secret | Purpose |
| --- | --- |
| `GITOPS_REPOSITORY_TOKEN` | Fine-grained GitHub token with **Contents: Read and write** access to `lackito/otel-demo-gitops`. |

The IAM role trust policy must restrict the GitHub OIDC subject to
`repo:lackito@6595109/otel-demo-apps@1305341394:ref:refs/heads/main`. This
repository uses GitHub's customized OIDC subject format with immutable owner and
repository IDs. The role needs only ECR push permissions for the
`recommendation` repository plus `ecr:GetAuthorizationToken`. The workflow
validates and displays its non-sensitive OIDC audience and subject before
attempting to assume the role.

The release workflow intentionally updates the GitOps repository rather than
deploying to Kubernetes directly. Argo CD remains the sole owner of workloads.
