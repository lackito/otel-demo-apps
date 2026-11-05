# Recommendation Service

This service recommends other products based on the currently selected product.

## Validation

The local release builds on native ARM64 and runs `smoke.py` before publishing
to GHCR or promoting the image to GitOps. CI also runs the test on native AMD64.
The image retains the pinned Python 3.14.6 / Alpine 3.23 base.

## Run locally

From the repository root, with Docker running and a Python environment containing
`grpcio==1.78.0` and `grpcio-tools==1.78.0`:

```sh
docker build -t otel-demo/recommendation:test apps/recommendation
python apps/recommendation/smoke.py otel-demo/recommendation:test
```

Use `--seconds 300` for a longer run. The test creates a disposable container
limited to the chart's 500 MiB memory budget. Local gRPC fixtures provide a catalog,
dynamic flag evaluation, and OTLP receivers. It checks concurrent recommendation
requests, excluded product IDs, gRPC health, traces, metrics, logs, and the absence
of the duplicate LoggerProvider warning. Telemetry exports run every 100 ms to
stress the background gRPC paths. The container is removed even if a check fails.

The test runner's gRPC version is independent of the version inside the image.
The application retains gRPC 1.82.1 and pins openfeature-provider-flagd to 0.2.3
with package hashes, matching the chart's flagd v1 evaluation API.

## Crash investigation

The previously deployed gRPC 1.82.1 image intermittently exited with code 139.
An isolated kind pod reproduced a segmentation fault under requests and rapid
telemetry export. A Debian comparison with the same dependency versions also
failed, reporting a native gRPC assertion in `call_combiner.cc`:
`prev_size >= 1u (0 vs. 1)`. Removing duplicate logging alone did not prevent
the crash. Thus changing the Linux distribution or logging alone was insufficient.

The pinned chart 0.38.4 runs flagd v0.12.8, which serves evaluation v1.
Provider 0.5.1 calls evaluation v2; direct v2 calls returned UNIMPLEMENTED
(HTTP 404), while v1 calls succeeded. Upgrading gRPC to 1.84.0 did not prevent
the native crash with the incompatible provider.

The fix restores provider 0.2.3, which uses evaluation v1. The smoke fixture
exposes only v1 and requires successful flag evaluations for every request;
the incompatible provider fails this check instead of passing with fallback
values. Automatic OpenTelemetry instrumentation owns the log provider and
handler; application code reuses the normal logger.
`PYTHONFAULTHANDLER=1` preserves Python thread stacks if a future native crash
occurs. Finite load tests do not guarantee indefinite stability.
