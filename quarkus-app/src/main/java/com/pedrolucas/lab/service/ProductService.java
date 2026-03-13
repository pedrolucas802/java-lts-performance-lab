package com.pedrolucas.lab.service;

import com.pedrolucas.lab.dto.ProductDTO;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@ApplicationScoped
public class ProductService {

    public List<ProductDTO> getProducts(int count) {
        List<ProductDTO> products = new ArrayList<>(count);

        for (int i = 0; i < count; i++) {
            Map<String, String> attributes = new HashMap<>();
            attributes.put("brand", "Brand-" + (i % 10));
            attributes.put("region", "Region-" + (i % 5));
            attributes.put("segment", "Segment-" + (i % 3));

            products.add(new ProductDTO(
                    i,
                    "Product-" + i,
                    "Category-" + (i % 20),
                    10.0 + (i % 100),
                    List.of("tag-" + (i % 4), "tag-" + (i % 6), "tag-" + (i % 8)),
                    attributes
            ));
        }

        return products;
    }
}