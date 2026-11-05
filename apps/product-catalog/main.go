// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
package main

//go:generate go install google.golang.org/protobuf/cmd/protoc-gen-go
//go:generate go install google.golang.org/grpc/cmd/protoc-gen-go-grpc
//go:generate protoc --go_out=./ --go-grpc_out=./ --proto_path=../../pb ../../pb/demo.proto
//go:generate go install github.com/open-feature/cli/cmd/openfeature@v0.4.0
//go:generate openfeature generate -o flags --package-name flags go

import (
	"context"
	"fmt"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc"
	"go.opentelemetry.io/contrib/instrumentation/google.golang.org/grpc/otelgrpc/filters"
	"go.opentelemetry.io/contrib/instrumentation/runtime"
	"go.opentelemetry.io/contrib/otelconf"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	otelcodes "go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/log/global"
	"go.opentelemetry.io/otel/trace"

	otelhooks "github.com/open-feature/go-sdk-contrib/hooks/open-telemetry/pkg"
	flagd "github.com/open-feature/go-sdk-contrib/providers/flagd/pkg"
	"github.com/open-feature/go-sdk/openfeature"
	pb "github.com/opentelemetry/opentelemetry-demo/src/product-catalog/genproto/oteldemo"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/reflection"
	"google.golang.org/grpc/status"

	flags "github.com/opentelemetry/opentelemetry-demo/src/product-catalog/flags"
	"google.golang.org/protobuf/encoding/protojson"
)

type productCatalog struct {
	pb.UnimplementedProductCatalogServiceServer
}

var (
	logger    *slog.Logger
	catalogMu sync.RWMutex
	products  []*pb.Product
)

func init() {
	logger = otelslog.NewLogger("product-catalog")
}

// Load a complete snapshot before replacing the last known good catalog.
// Glob ignores Kubernetes' hidden ConfigMap revision directories.
func reloadProducts(dir string) error {
	files, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		return err
	}
	if len(files) == 0 {
		return fmt.Errorf("no catalog JSON files in %s", dir)
	}
	var next []*pb.Product
	seen := map[string]bool{}
	for _, file := range files {
		data, err := os.ReadFile(file)
		if err != nil {
			return err
		}
		var response pb.ListProductsResponse
		if err := protojson.Unmarshal(data, &response); err != nil {
			return fmt.Errorf("%s: %w", file, err)
		}
		for _, product := range response.Products {
			if product.Id == "" || seen[product.Id] {
				return fmt.Errorf("missing or duplicate product ID in %s", file)
			}
			seen[product.Id] = true
			next = append(next, product)
		}
	}
	if len(next) == 0 {
		return fmt.Errorf("empty product catalog")
	}
	catalogMu.Lock()
	products = next
	catalogMu.Unlock()
	return nil
}

func main() {
	ctx := context.Background()

	// Initialize OpenTelemetry SDK with otelconf
	sdk, err := otelconf.NewSDK(otelconf.WithContext(ctx))
	if err != nil {
		logger.Error(fmt.Sprintf("Failed to initialize OpenTelemetry SDK: %v", err))
		os.Exit(1)
	}
	defer func() {
		if err := sdk.Shutdown(ctx); err != nil {
			logger.Error(fmt.Sprintf("Error shutting down OpenTelemetry SDK: %v", err))
		}
		logger.Info("Shutdown OpenTelemetry SDK")
	}()

	// Set global providers and propagator
	otel.SetTracerProvider(sdk.TracerProvider())
	otel.SetMeterProvider(sdk.MeterProvider())
	global.SetLoggerProvider(sdk.LoggerProvider())
	otel.SetTextMapPropagator(sdk.Propagator())

	dir := os.Getenv("PRODUCT_CATALOG_PRODUCTS_PATH")
	if dir == "" {
		dir = "products"
	}
	interval := 10
	if value := os.Getenv("PRODUCT_CATALOG_RELOAD_INTERVAL"); value != "" {
		interval, err = strconv.Atoi(value)
		if err != nil || interval <= 0 {
			logger.Error("Invalid catalog reload interval")
			os.Exit(1)
		}
	}
	if err := reloadProducts(dir); err != nil {
		logger.Error(err.Error())
		os.Exit(1)
	}
	reloadCtx, stopReload := context.WithCancel(ctx)
	defer stopReload()
	go func() {
		ticker := time.NewTicker(time.Duration(interval) * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-reloadCtx.Done():
				return
			case <-ticker.C:
				if err := reloadProducts(dir); err != nil {
					logger.Error("Catalog reload failed; retaining previous snapshot", "error", err)
				}
			}
		}
	}()

	openfeature.AddHooks(otelhooks.NewTracesHook())
	provider, err := flagd.NewProvider()
	if err != nil {
		logger.Error("Error creating flagd provider", slog.Any("error", err))
	}

	err = openfeature.SetProvider(provider)
	if err != nil {
		logger.Error("Failed to set flagd as the provider", slog.Any("error", err))
	}
	defer openfeature.Shutdown()

	err = runtime.Start(runtime.WithMinimumReadMemStatsInterval(time.Second))
	if err != nil {
		logger.Error(err.Error())
	}

	svc := &productCatalog{}
	var port string
	mustMapEnv(&port, "PRODUCT_CATALOG_PORT")

	logger.Info(fmt.Sprintf("Product Catalog gRPC server started on port: %s", port))

	ln, err := net.Listen("tcp", fmt.Sprintf(":%s", port))
	if err != nil {
		logger.Error(fmt.Sprintf("TCP Listen: %v", err))
		os.Exit(1)
	}

	srv := grpc.NewServer(
		grpc.StatsHandler(otelgrpc.NewServerHandler(
			otelgrpc.WithFilter(filters.Not(filters.HealthCheck())),
		)),
	)

	reflection.Register(srv)

	pb.RegisterProductCatalogServiceServer(srv, svc)

	healthcheck := health.NewServer()
	healthpb.RegisterHealthServer(srv, healthcheck)

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM, syscall.SIGKILL)
	defer cancel()

	go func() {
		if err := srv.Serve(ln); err != nil {
			logger.Error(fmt.Sprintf("Failed to serve gRPC server, err: %v", err))
		}
	}()

	<-ctx.Done()

	srv.GracefulStop()
	logger.Info("Product Catalog gRPC server stopped")
}

func loadProducts(ctx context.Context) ([]*pb.Product, error) {
	catalogMu.RLock()
	defer catalogMu.RUnlock()
	return append([]*pb.Product(nil), products...), nil
}

func searchProducts(ctx context.Context, query string) ([]*pb.Product, error) {
	all, _ := loadProducts(ctx)
	var result []*pb.Product
	query = strings.ToLower(query)
	for _, product := range all {
		if strings.Contains(strings.ToLower(product.Name), query) || strings.Contains(strings.ToLower(product.Description), query) {
			result = append(result, product)
		}
	}
	return result, nil
}

func getProduct(ctx context.Context, id string) (*pb.Product, error) {
	all, _ := loadProducts(ctx)
	for _, product := range all {
		if product.Id == id {
			return product, nil
		}
	}
	return nil, fmt.Errorf("product not found")
}

func mustMapEnv(target *string, key string) {
	value, present := os.LookupEnv(key)
	if !present {
		logger.Error(fmt.Sprintf("Environment Variable Not Set: %q", key))
	}
	*target = value
}

func (p *productCatalog) Check(ctx context.Context, req *healthpb.HealthCheckRequest) (*healthpb.HealthCheckResponse, error) {
	return &healthpb.HealthCheckResponse{Status: healthpb.HealthCheckResponse_SERVING}, nil
}

func (p *productCatalog) Watch(req *healthpb.HealthCheckRequest, ws healthpb.Health_WatchServer) error {
	return status.Errorf(codes.Unimplemented, "health check via Watch not implemented")
}

func (p *productCatalog) ListProducts(ctx context.Context, req *pb.Empty) (*pb.ListProductsResponse, error) {
	span := trace.SpanFromContext(ctx)

	products, err := loadProducts(ctx)
	if err != nil {
		span.SetStatus(otelcodes.Error, err.Error())
		return nil, status.Errorf(codes.Internal, "failed to load products: %v", err)
	}

	span.SetAttributes(
		attribute.Int("demo.product.count", len(products)),
	)
	return &pb.ListProductsResponse{Products: products}, nil
}

func (p *productCatalog) GetProduct(ctx context.Context, req *pb.GetProductRequest) (*pb.Product, error) {
	span := trace.SpanFromContext(ctx)
	span.SetAttributes(
		attribute.String("demo.product.id", req.Id),
	)

	// GetProduct will fail on a specific product when feature flag is enabled
	if p.checkProductFailure(ctx, req.Id) {
		msg := "Error: Product Catalog Fail Feature Flag Enabled"
		span.SetStatus(otelcodes.Error, msg)
		span.AddEvent(msg)
		return nil, status.Error(codes.Internal, msg)
	}

	found, err := getProduct(ctx, req.Id)
	if err != nil {
		msg := fmt.Sprintf("Product Not Found: %s", req.Id)
		span.SetStatus(otelcodes.Error, msg)
		span.AddEvent(msg)
		return nil, status.Error(codes.NotFound, msg)
	}

	span.AddEvent("Product Found")
	span.SetAttributes(
		attribute.String("demo.product.id", req.Id),
		attribute.String("demo.product.name", found.Name),
	)

	logger.LogAttrs(
		ctx,
		slog.LevelInfo, "Product Found",
		slog.String("demo.product.name", found.Name),
		slog.String("demo.product.id", req.Id),
	)

	return found, nil
}

func (p *productCatalog) SearchProducts(ctx context.Context, req *pb.SearchProductsRequest) (*pb.SearchProductsResponse, error) {
	span := trace.SpanFromContext(ctx)

	result, err := searchProducts(ctx, req.Query)
	if err != nil {
		span.SetStatus(otelcodes.Error, err.Error())
		return nil, status.Errorf(codes.Internal, "failed to search products: %v", err)
	}

	span.SetAttributes(
		attribute.Int("demo.product.search.count", len(result)),
	)
	return &pb.SearchProductsResponse{Results: result}, nil
}

func (p *productCatalog) checkProductFailure(ctx context.Context, id string) bool {
	return flags.ProductCatalogFailure.Value(ctx, openfeature.NewTargetlessEvaluationContext(map[string]any{"product_id": id}))
}
