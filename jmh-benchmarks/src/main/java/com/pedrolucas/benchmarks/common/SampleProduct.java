package com.pedrolucas.benchmarks.common;

public record SampleProduct(
        long id,
        String name,
        String category,
        double price,
        String description
) {
}