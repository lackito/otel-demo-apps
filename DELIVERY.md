# Custom service delivery (chart 0.38.4)

Product Catalog and Ad now have build and AWS release paths alongside
Recommendation. This implements delivery; it is not evidence of an ECR publish
or an EKS rollout. The upstream chart remains pinned at 0.38.4. No PostgreSQL
is required. The local/GHCR Recommendation workflow is unchanged.

## Build and validate

Run from the repository root, with Docker, Go, Python 3.12, and Helm installed.
Use Python 3.12 explicitly (matching CI); the pinned gRPC packages do not
provide Python 3.15 wheels. The binary-only install avoids a local C++ build:

```sh
python3.12 -m venv .venv-smoke
. .venv-smoke/bin/activate
python -m pip install --only-binary=:all: ruamel.yaml==0.18.16 grpcio==1.78.0 grpcio-tools==1.78.0
python -m unittest discover -s tests -v
(cd apps/product-catalog && go test -race ./...)
python scripts/check_chart.py
docker build -f apps/product-catalog/Dockerfile -t catalog:test .
docker build -f apps/ad/Dockerfile -t ad:test .
python scripts/smoke.py product-catalog catalog:test
python scripts/smoke.py ad ad:test
```

Smoke checks start disposable containers, use an ephemeral local telemetry
receiver, and check real gRPC requests, health, and OTLP traces, metrics, and
logs. Ad uses HTTP/protobuf; Catalog uses gRPC, matching the chart. Docker must
be able to reach the host through `host.docker.internal`. Tests use the chart's
memory limits. They do not establish production load capacity or EKS health.
For local CPU emulation only, `SMOKE_MEMORY_LIMIT` can override the limit;
a pass with that override does not validate the chart memory budget. CI uses
the default chart limits on native x86-64 runners.
The catalog fixture is the exact chart 0.38.4 `products/products.json`.

Catalog reads every `*.json` file under `/usr/src/app/products`, configurable
with `PRODUCT_CATALOG_PRODUCTS_PATH`. It loads a valid snapshot before serving,
then reloads every `PRODUCT_CATALOG_RELOAD_INTERVAL` seconds (default 10).
Malformed, empty, or duplicate-ID updates retain the previous snapshot and log
an error. Startup with invalid data fails. List, Get, Search, health, feature
flags, and gRPC tracing remain available. The image includes an OTEL config
file because the newer SDK needs one; it consumes the chart's OTLP endpoint,
service name, and resource attributes. `OTEL_CONFIG_FILE` can override it.

Ad vendors the missing protocol input under `pb/`. The agent is pinned to
2.31.1 and verified by SHA-256 during build. See `pb/README.md` for provenance.

## Rollout order (operator action)

1. Review and apply infrastructure layer 04 after a saved Terraform plan.
   Expect two additional ECR repositories and publisher roles; no existing
   repository, Recommendation role, or OIDC provider replacement. The existing
   Recommendation role gets repository-scoped pull/inspection permissions.
2. Configure `GITOPS_REPOSITORY_TOKEN` in this repository with contents-write
   permission only for `lackito/otel-demo-gitops`; it must be able to update
   `main` under that repository's branch rules. AWS uses OIDC, not static keys.
3. Review application changes before merging to `main`: **the merge triggers
   the path-filtered release workflows and can activate images through Argo CD**.
   Manual dispatch is allowed only on main. CI must pass first.
4. Each release builds an image tagged with the full source SHA, pushes ECR,
   pulls it back, and smoke-tests it before GitOps promotion. Immutable SHA
   tags for Ad/Catalog allow reruns to reuse an existing image. Failed smoke
   tests do not promote. A rerun must use the same immutable source SHA.
5. Promotion edits only `components.<service>.imageOverride`. A normal push
   rejected because another service won the race is retried by fetching main
   and replaying only that component edit. No force pushes. After eight failed
   attempts the workflow fails visibly. Branch protection/authentication errors
   require operator correction; published images can remain unpromoted.
6. Observe Argo CD sync/health, Deployment rollout, actual pod image IDs, gRPC
   health, storefront catalog/search/ads, logs, traces, and metrics in EKS.
   Verify the expected image digest against ECR, not just the tag. Check
   resource usage under realistic traffic. Record actual release and rollout
   evidence in the GitOps operations log.

Recommendation continues its existing release behavior, with verified ECR
availability and safer per-component promotion. New-service smoke checks do
not change Recommendation's runtime configuration.

For rollback, revert only the affected component's GitOps image override to a
previous verified SHA; preserve other services' changes. For the first custom
release, removing that service's `imageOverride` restores the chart image.
Argo CD owns workload reconciliation; do not install a competing Helm release.
Do not hand-edit an active override to a placeholder or unpublished image.

The shared main-only OIDC subject is
`repo:lackito@6595109/otel-demo-apps@1305341394:ref:refs/heads/main`, audience
`sts.amazonaws.com`. Each publisher role is restricted to its ECR repository;
code on trusted main can request any of these roles, so repository permissions
and workflow review remain part of the trust boundary.

Separate existing issue: OpenSearch is disabled while the default Collector
logs pipeline still points at it. This change does not repair that pipeline;
local receipt of OTLP logs does not prove downstream cluster log storage.


## Local validation recorded October 24, 2026

Both custom images passed the Docker gRPC, health, and OTLP traces/metrics/logs
smoke tests on ARM64. A Python 3.15 environment attempted a native gRPC build
and failed on a missing C++ header; the documented Python 3.12 binary-only
installation succeeded. Release workflows also select Python 3.12 explicitly.

The `kind-otel-demo-local` ARM64 cluster ran `otel-demo/product-catalog:local`
and `otel-demo/ad:local`, loaded directly into kind. Temporary Helm parameters
on the `otel-demo-local` Argo CD Application selected these repositories/tags
with pullPolicy Never. The chart remained 0.38.4. The application validation
reported healthy rollouts; subsequent Jaeger API inspection confirmed spans
from both custom services, including GetAds, ListProducts, and GetProduct at
approximately 16:59 EDT. The user then confirmed traces were visible in the UI.
These are session observations, not immutable image-release provenance: the
`:local` tags are mutable and were built before these commits.

The temporary Application parameters are not committed GitOps desired state.
Removing `/spec/sources/0/helm/parameters` restores Git/chart defaults only
while that list contains solely these test overrides. Inspect it before removal
so unrelated future parameters are preserved. A Terraform apply may also
reconcile the Application specification.

Still outstanding: native AMD64 validation at chart memory limits; sustained
load validation; ECR publication and EKS verification; permanent local GHCR
release/promotion for Ad and Catalog. The reported frontend-proxy:ingress error
is deferred, with its cause not established. Collector log export to disabled
OpenSearch remains a separate known issue. Successful Jaeger traces do not
establish log-storage health.

## Pre-PR branch comparison

On October 24, refreshed origin/main was d5a201b911916a645c0e9cebb62cbe76ee2332d7;
the local main ref was older (9cc0037d720c94eafbca39144f401abee5685801).
This implementation branch started at local-branch commit a27781865d22bfbe1398e82a04c5641bd19140bb,
carrying 20 commits absent from origin/main's ancestry. Before implementation,
the net tree difference against origin/main was only the Recommendation updater
and tests under `.github/scripts/`, plus their CI invocation; those are retained.
Before opening a main-targeted PR, prepare a clean branch from refreshed
origin/main and deliberately include or omit those existing local-only checks.
Do not blindly merge the full local history. No PR or remote push was made
as part of this local commit preparation.
