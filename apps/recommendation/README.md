# Recommendation service

Returns recommendations from Product Catalog, excluding the requested product
IDs. Uses the Python flagd provider from upstream 3.1.0 with chart 0.42.6.

## Build and test

From the repository root, with the test environment in [DELIVERY.md](../../DELIVERY.md):

```bash
docker build -t recommendation:test apps/recommendation
python apps/recommendation/smoke.py recommendation:test
```

The test uses a disposable container with the chart's 500 MiB memory budget,
a mock catalog, flagd v0.16.0, and OTLP receivers. It checks concurrent
requests, excluded products, health, flag evaluation, and all three telemetry
signals. It runs for 120 seconds; add `--seconds 300` for a longer check.

## Runtime requirements

Keep dependency hashes in `requirements.txt` in sync with `requirements.in`.
Automatic OpenTelemetry instrumentation owns
the log provider and handler; application code uses the standard logger.
`PYTHONFAULTHANDLER=1` enables Python stack diagnostics for native failures.

Use the service's kind or AWS release workflow to publish and promote its image.
See [branching](../../docs/BRANCHING.md) and [delivery](../../DELIVERY.md).
