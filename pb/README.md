# Protocol provenance

`demo.proto`, the root Apache-2.0 LICENSE, and Product Catalog's adapted
`otel-config.yaml` originate from open-telemetry/opentelemetry-demo commit
`2c4be61741536937f1486ecaf74f44dbfd15d707` (2026-10-21).
Copyright and license headers are retained. Ad uses Java agent 2.31.1,
the version pinned in that commit's `.env`. Product Catalog and Ad RPCs
are wire-compatible with the chart 0.38.4 demo APIs; smoke tests exercise them.
Build both Dockerfiles with this repository root as context.

The catalog test fixture is copied without modification from the published
OpenTelemetry Demo Helm chart 0.38.4 (`products/products.json`). The chart
compatibility check verifies that fixture against the downloaded chart.
