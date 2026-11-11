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

For Ad, the smoke test also runs `apps/ad/test_flagd.py` with the same image.
This starts a separate flagd v0.16.0 container (the
server used by chart 0.42.6) and switches `adHighCpu` from false to true.
It verifies that Ad acts on the flag instead of silently using its false
fallback.

## Metrics

The service emits OpenTelemetry custom metrics over OTLP. It also exposes
Prometheus-client metrics on `AD_PROMETHEUS_PORT` (default 9465). The Collector
can scrape that endpoint into its metrics pipeline. These are two instrumentation
paths within this service.

Use the service's kind or AWS release workflow to publish and promote its image.
See [branching](../../docs/BRANCHING.md) and [delivery](../../DELIVERY.md).
