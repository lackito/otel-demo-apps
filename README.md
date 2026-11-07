# otel-demo-apps

Application source, Dockerfiles, tests, and release workflows for the
[OpenTelemetry Demo](https://opentelemetry.io/docs/demo/).

The custom services are **Ad**, **Product Catalog**, and **Recommendation**.
Other demo services come from the pinned upstream Helm chart.

## Release targets

| Source branch | Image registry | Deployment configuration |
| --- | --- | --- |
| `kind` | Public GHCR packages, `otel-demo-kind-<service>` | [otel-demo-gitops-kind](https://github.com/lackito/otel-demo-gitops-kind) |
| `main` | Amazon ECR repositories named after each service | [otel-demo-gitops-aws](https://github.com/lackito/otel-demo-gitops-aws) |

Each service has its own AWS and kind release workflow. A service-only change
releases that service; changes to shared release files can trigger several.
Workflows build and test images, publish them, and update GitOps. Argo CD then
updates the cluster.

## GitHub Actions settings

Configure these in this repository:

| Setting | Purpose |
| --- | --- |
| `KIND_GITOPS_REPOSITORY_TOKEN` secret | Contents read/write for `otel-demo-gitops-kind` |
| `AWS_GITOPS_REPOSITORY_TOKEN` secret | Contents read/write for `otel-demo-gitops-aws` |
| `AWS_RELEASES_ENABLED` variable | Set to `true` only when AWS infrastructure is ready |

GHCR publishing uses the automatic `GITHUB_TOKEN` with `packages: write`.
There is no registry PAT or infrastructure-repository token to configure.
AWS publishing uses GitHub OIDC and the Terraform-managed IAM role for each
service. Kind packages must be public for anonymous cluster pulls.

## Guides

- [Branching](docs/BRANCHING.md): develop, test on kind, and review into main.
- [Build and release](DELIVERY.md): commands for all three services and verification.
- [Names and repositories](docs/NAMING.md): a short reference for both environments.

Each service directory has its own README for service-specific details.
