# Product Catalog service

Provides gRPC list, get, and search operations for products loaded from JSON.
The chart mounts product data at `/usr/src/app/products`; this custom service
does not use PostgreSQL.

## Build and test

From the repository root, with the test environment in [DELIVERY.md](../../DELIVERY.md):

```bash
(cd apps/product-catalog && go test -race ./...)
docker build -f apps/product-catalog/Dockerfile -t catalog:test .
python scripts/smoke.py product-catalog catalog:test
```

The smoke test checks catalog responses, health, and OTLP traces, metrics, and logs.

## Configuration

| Setting | Default |
| --- | --- |
| `PRODUCT_CATALOG_PORT` | Supplied by the chart: `8080` |
| `PRODUCT_CATALOG_PRODUCTS_PATH` | `products` relative to the working directory |
| `PRODUCT_CATALOG_RELOAD_INTERVAL` | `10` seconds |
| `OTEL_CONFIG_FILE` | Image sets `/usr/src/app/otel-config.yaml` |

The service loads `*.json` files before serving and reloads them periodically.
Invalid, empty, or duplicate-ID updates keep the last valid snapshot and log an
error. Invalid startup data prevents the service from starting.

The image's OpenTelemetry configuration reads the chart's endpoint, resource
attributes, and service name. Product Catalog uses OTLP/gRPC. See
[protocol provenance](../../pb/README.md) for the protocol and catalog fixture.

Use the service's kind or AWS release workflow to publish and promote its image.
See [branching](../../docs/BRANCHING.md) and [delivery](../../DELIVERY.md).
