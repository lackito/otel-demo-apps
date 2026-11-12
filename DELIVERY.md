# Build and release

Ad, Product Catalog, and Recommendation are built from this repository and
run with OpenTelemetry Demo Helm chart **0.38.4**. See [branching](docs/BRANCHING.md)
for the feature → kind → main workflow.

## Build and test locally

Use Docker, Go, Helm, and Python 3.12. Run from the repository root:

```bash
python3.12 -m venv .venv-smoke
. .venv-smoke/bin/activate
python -m pip install --only-binary=:all: ruamel.yaml==0.18.16 grpcio==1.78.0 grpcio-tools==1.78.0
python -m unittest discover -s tests -v
(cd apps/product-catalog && go test -race ./...)
python scripts/check_chart.py

docker build -f apps/ad/Dockerfile -t ad:test .
docker build -f apps/product-catalog/Dockerfile -t catalog:test .
docker build -t recommendation:test apps/recommendation
python scripts/smoke.py ad ad:test
python apps/product-catalog/smoke.py catalog:test
python apps/recommendation/smoke.py recommendation:test
```

The smoke tests check requests, gRPC health, and OTLP traces, metrics, and logs
at a local test receiver. Recommendation also checks flagd-v1 evaluation under
concurrent requests for 120 seconds. Containers use the chart's service memory
budgets. These tests do not verify a cluster's telemetry storage.

Python 3.12 matches CI and has wheels for the pinned test dependencies. Docker
must be able to reach the test host through `host.docker.internal`. CI runs
native ARM64 and AMD64 checks; kind publishing builds ARM64 images.

## Release a service

| Target | Branch | Workflow file | Registry |
| --- | --- | --- | --- |
| kind | `kind` | `<service>-kind-release.yml` | GHCR `otel-demo-kind-<service>` |
| AWS | `main` | `<service>-aws-release.yml` | ECR `<service>` |

Replace `<service>` with `ad`, `product-catalog`, or `recommendation`.
A matching source change starts its release, or you can dispatch the workflow
manually. Shared-file changes, including `scripts/promote.py`, can start all three.
Each image is tagged with its full source commit SHA.

Kind needs a running platform, public GHCR packages, and
`KIND_GITOPS_REPOSITORY_TOKEN` with write access to kind GitOps. Publication
uses the automatic `GITHUB_TOKEN`. If the first anonymous pull fails, make the
new package public and rerun the workflow.

AWS needs infrastructure layers 02, 03, and 04, the shared GitHub OIDC provider,
`AWS_GITOPS_REPOSITORY_TOKEN`, and `AWS_RELEASES_ENABLED=true`. Each service uses
its own ECR publisher role. No static AWS access keys are needed by the workflows.

The AWS OIDC audience is `sts.amazonaws.com` and the trusted subject is:

```text
repo:lackito@6595109/otel-demo-apps@1305341394:ref:refs/heads/main
```

Release checks must pass before promotion. `scripts/promote.py --target kind|aws`
updates only the chosen service's image override, preserving other settings and
retrying concurrent Git pushes. A failed promotion can leave a published image
without changing the deployed application. Inspect the failed step before rerunning.

## Verify deployment

1. Confirm the service's release job succeeded.
2. Check its generated `chore(<service>): deploy <sha>` commit in the target GitOps repo.
3. Run `make application-validate` from the target environment's infrastructure repository.
4. Compare the deployed tag with the release SHA and the running image digest
   with the published platform image. A tagged image index can have a different
   digest from the platform image it references.
5. Exercise the storefront and inspect traces, metrics, and logs.

Kind stores application logs in OpenSearch. AWS OpenSearch is disabled and its
Collector still has an OpenSearch logs exporter; AWS log storage needs separate
configuration. Healthy rollouts alone do not verify downstream telemetry.

After recreating ECR repositories, run **all three** AWS release workflows.
Terraform creates repositories and roles, not images; old GitOps tags may be
unavailable until the releases publish and promote them.

## Rollback

Revert only the affected service's image override to a verified image that still
exists. Preserve unrelated releases. Argo CD applies the GitOps change. Removing
an override restores that service's pinned upstream chart image.

## Service details

- [Ad](apps/ad/README.md): contextual ads, Java agent, and custom metrics.
- [Product Catalog](apps/product-catalog/README.md): PostgreSQL-backed products and live queries.
- [Recommendation](apps/recommendation/README.md): catalog-backed recommendations and flagd compatibility.
- [Protocol provenance](pb/README.md): upstream sources and licenses.

