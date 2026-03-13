package com.pedrolucas.benchmarks.common;

import java.util.ArrayList;
import java.util.List;

public final class SampleDataFactory {

    private SampleDataFactory() {
    }

    public static List<SampleProduct> createProducts(int size) {
        List<SampleProduct> products = new ArrayList<>(size);
        for (int i = 0; i < size; i++) {
            products.add(new SampleProduct(
                    i,
                    "Product-" + i,
                    "Category-" + (i % 10),
                    10.0 + (i % 100),
                    "Description for product " + i
            ));
        }
        return products;
    }
}