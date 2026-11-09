# Names and repositories

Repository names follow `otel-demo-<responsibility>-<target>`. Application
source is shared in `otel-demo-apps`.

| Responsibility | AWS | kind |
| --- | --- | --- |
| Infrastructure | `otel-demo-infra-aws` | `otel-demo-infra-kind` |
| GitOps | `otel-demo-gitops-aws` | `otel-demo-gitops-kind` |
| Application source branch | `main` | `kind` |
| Cluster | `otel-demo-aws-dev` | `otel-demo` |
| kubectl context used by the guides | `otel-demo-aws` | `kind-otel-demo` |
| Argo Application | `otel-demo-aws` | `otel-demo-kind` |
| Images | ECR `<service>` | GHCR `otel-demo-kind-<service>` |

The custom service names are `ad`, `product-catalog`, and `recommendation`.
AWS publisher roles follow `otel-demo-aws-dev-<service>-github-actions`.

The Helm release is `otel-demo`, the namespace is `opentelemetry-demo`, and the
GitOps values path is `applications/otel-demo/values.yaml` in both environments.
These identify the shared application rather than its hosting platform.

kind generates its context name by prefixing the cluster name with `kind-`.
The AWS guide creates the shorter `otel-demo-aws` context alias explicitly.
