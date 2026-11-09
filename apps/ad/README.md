# Ad service

Returns contextual ads for supplied keys, or random ads when no keys are given.
It exposes gRPC on `AD_PORT` and uses the pinned Java agent for instrumentation.

## Build and test

From the repository root, with the test environment in [DELIVERY.md](../../DELIVERY.md):

```bash
docker build -f apps/ad/Dockerfile -t ad:test .
python scripts/smoke.py ad ad:test
```

The Docker build uses the repository-root `pb/` protocol input. The smoke test
checks targeted/random ad responses, gRPC health, and OTLP traces, metrics, and logs.

## Metrics

The service emits OpenTelemetry custom metrics over OTLP. It also exposes
Prometheus-client metrics on `AD_PROMETHEUS_PORT` (default 9465). The Collector
can scrape that endpoint into its metrics pipeline. These are two instrumentation
paths within this service.

Use the service's kind or AWS release workflow to publish and promote its image.
See [branching](../../docs/BRANCHING.md) and [delivery](../../DELIVERY.md).
