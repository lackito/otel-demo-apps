# otel-demo-apps

Shared application source, Dockerfiles, regression tests, and image-release
workflows for the OpenTelemetry Demo. Infrastructure and deployment desired
state live in separate repositories.

| Responsibility | AWS | kind |
| --- | --- | --- |
| Infrastructure | [otel-demo-infra-aws](https://github.com/lackito/otel-demo-infra-aws) | [otel-demo-infra-kind](https://github.com/lackito/otel-demo-infra-kind) |
| Deployment desired state | [otel-demo-gitops-aws](https://github.com/lackito/otel-demo-gitops-aws) | [otel-demo-gitops-kind](https://github.com/lackito/otel-demo-gitops-kind) |
| Application source branch | `main` | `kind` |
| Images | Amazon ECR, full Git SHA tags | Public GHCR `otel-demo-kind-<service>`, full Git SHA tags |
| Argo CD Application | `otel-demo-aws` | `otel-demo-kind` |

Recommendation, Product Catalog, and Ad each have their own
`<service>-aws-release.yml` and `<service>-kind-release.yml` workflows. A service
source change releases that service; changing the shared promotion script can
release all three. CI builds and tests both native ARM64 and AMD64 images.

## Release configuration

| Setting in this repository | Purpose |
| --- | --- |
| `AWS_GITOPS_REPOSITORY_TOKEN` secret | Contents read/write for `lackito/otel-demo-gitops-aws` |
| `KIND_GITOPS_REPOSITORY_TOKEN` secret | Contents read/write for `lackito/otel-demo-gitops-kind` |
| `GHCR_PAT` secret | Package publication; existing classic PAT with `write:packages` |
| `AWS_RELEASES_ENABLED` Actions variable | Set to `true` after AWS infrastructure and publisher roles are rebuilt; AWS release jobs otherwise skip |

AWS releases use main-only GitHub OIDC and repository-scoped ECR publisher roles.
The trusted application identity remains
`repo:lackito@6595109/otel-demo-apps@1305341394:ref:refs/heads/main`.
Kind releases run on native ARM64, verify anonymous package access, and update
kind GitOps. Make each new GHCR package public before rerunning its first
publication if the anonymous-access check fails.

Both release paths test real requests, health, and OTLP signals before GitOps
promotion. `scripts/promote.py --target aws|kind` changes only the selected
service and retries competing ordinary pushes against GitOps main. Argo CD
reconciles the resulting commit. CI does not deploy directly to Kubernetes.

## Build, verify, and migrate

- [DELIVERY.md](DELIVERY.md): pinned-chart compatibility, builds, regression tests, promotion, verification, and rollback.
- [Naming migration](docs/NAMING.md): repository rename order, secret names, kind branch bootstrap, and resource identities.
- [Architecture walkthrough](https://github.com/lackito/otel-demo-infra-kind/blob/main/docs/ARCHITECTURE.md): shared delivery model and ownership boundaries.
