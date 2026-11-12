# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM --platform=${BUILDPLATFORM} docker.io/library/golang:1.26.5-bookworm@sha256:1ecb7edf62a0408027bd5729dfd6b1b8766e578e8df93995b225dfd0944eb651 AS builder

WORKDIR /usr/src/app/

COPY ./apps/product-catalog/go.mod go.mod
COPY ./apps/product-catalog/go.sum go.sum

RUN go mod download

COPY ./apps/product-catalog/genproto/oteldemo/ genproto/oteldemo/
COPY ./apps/product-catalog/flags/ flags/
COPY ./apps/product-catalog/main.go ./apps/product-catalog/opamp.go ./

ARG TARGETOS
ARG TARGETARCH
RUN CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} GO111MODULE=on go build -ldflags "-s -w" -o product-catalog .

FROM ghcr.io/grpc-ecosystem/grpc-health-probe:v0.4.53@sha256:a732f1b3a737926c2902393809b344c9f293b62f7069dbd0614caebd298b2e8d AS grpc-health-probe

FROM gcr.io/distroless/static-debian12:nonroot@sha256:aef9602f8710ec12bde19d593fed1f76c708531bb7aba205110f1029786ead7b
LABEL io.otel-demo.release-test="product-catalog-1"

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/product-catalog ./
COPY --from=grpc-health-probe /ko-app/grpc-health-probe /bin/grpc_health_probe

COPY ./apps/product-catalog/otel-config.yaml ./otel-config.yaml
ENV OTEL_CONFIG_FILE=/usr/src/app/otel-config.yaml
EXPOSE 8080
ENTRYPOINT [ "./product-catalog" ]
