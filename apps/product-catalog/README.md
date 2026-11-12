# Product Catalog service

Provides gRPC list, get, and search operations against `catalog.products` in
PostgreSQL. Chart 0.42.6 initializes the catalog in `astronomy_db` and supplies
`DB_CONNECTION_STRING`, the gRPC port and the mounted OpenTelemetry config.

## Build and test

From the repository root, with the test environment in [DELIVERY.md](../../DELIVERY.md):

```bash
(cd apps/product-catalog && go test -race ./...)
docker build -f apps/product-catalog/Dockerfile -t catalog:test .
python apps/product-catalog/smoke.py catalog:test
```

The smoke test checks catalog responses, health, and OTLP traces, metrics, and logs.

The smoke test starts an isolated PostgreSQL 18.4 container, seeds the 3.1.0
catalog, then updates a row and verifies the change through gRPC.
