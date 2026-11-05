package main

import (
	"context"
	"net"
	"os"
	"path/filepath"
	"sync"
	"testing"

	pb "github.com/opentelemetry/opentelemetry-demo/src/product-catalog/genproto/oteldemo"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
)

func TestCatalogRPCAndReload(t *testing.T) {
	dir := t.TempDir()
	data, err := os.ReadFile("../../tests/fixtures/products.json")
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "products.json")
	if err := os.WriteFile(path, data, 0600); err != nil {
		t.Fatal(err)
	}
	if err := reloadProducts(dir); err != nil {
		t.Fatal(err)
	}
	listener := bufconn.Listen(1024 * 1024)
	server := grpc.NewServer()
	pb.RegisterProductCatalogServiceServer(server, &productCatalog{})
	go server.Serve(listener)
	defer server.Stop()
	conn, err := grpc.NewClient("passthrough:///catalog", grpc.WithTransportCredentials(insecure.NewCredentials()), grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return listener.Dial() }))
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	client := pb.NewProductCatalogServiceClient(conn)
	ctx := context.Background()
	listed, err := client.ListProducts(ctx, &pb.Empty{})
	if err != nil || len(listed.Products) == 0 {
		t.Fatalf("list: %v %v", listed, err)
	}
	first := listed.Products[0]
	got, err := client.GetProduct(ctx, &pb.GetProductRequest{Id: first.Id})
	if err != nil || got.Name != first.Name || got.PriceUsd == nil {
		t.Fatalf("get: %v %v", got, err)
	}
	_, err = client.GetProduct(ctx, &pb.GetProductRequest{Id: "missing"})
	if status.Code(err) != codes.NotFound {
		t.Fatalf("missing: %v", err)
	}
	result, err := client.SearchProducts(ctx, &pb.SearchProductsRequest{Query: "EXPLORASCOPE"})
	if err != nil || len(result.Results) == 0 {
		t.Fatalf("search: %v %v", result, err)
	}
	// Bad, empty, and duplicate updates must leave the last good snapshot intact.
	for _, invalid := range []string{`{`, `{"products":[]}`, `{"products":[{"id":"a"},{"id":"a"}]}`} {
		os.WriteFile(path, []byte(invalid), 0600)
		if reloadProducts(dir) == nil {
			t.Fatal("accepted invalid catalog")
		}
		current, _ := client.ListProducts(ctx, &pb.Empty{})
		if len(current.Products) != len(listed.Products) {
			t.Fatal("lost previous catalog")
		}
	}
	os.WriteFile(path, []byte(`{"products":[{"id":"new","name":"Replacement"}]}`), 0600)
	var wg sync.WaitGroup
	for range 8 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for range 20 {
				client.ListProducts(ctx, &pb.Empty{})
			}
		}()
	}
	if err := reloadProducts(dir); err != nil {
		t.Fatal(err)
	}
	wg.Wait()
	current, _ := client.ListProducts(ctx, &pb.Empty{})
	if len(current.Products) != 1 || current.Products[0].Id != "new" {
		t.Fatal("reload did not replace catalog")
	}
	if reloadProducts(t.TempDir()) == nil {
		t.Fatal("accepted missing files")
	}
}
