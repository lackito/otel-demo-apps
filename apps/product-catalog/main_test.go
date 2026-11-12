package main

import "testing"

func TestProductRow(t *testing.T) {
	p := parseProductRow("id", "name", "", "", "USD", "telescopes, accessories", 101, 960000000)
	if p.PriceUsd.Units != 101 || p.PriceUsd.Nanos != 960000000 || len(p.Categories) != 2 || p.Categories[1] != "accessories" {
		t.Fatalf("unexpected product: %v", p)
	}
}
