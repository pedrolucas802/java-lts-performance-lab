package com.pedrolucas.lab.dto;

import java.util.List;
import java.util.Map;

public record ProductDTO(
        long id,
        String name,
        String category,
        double price,
        List<String> tags,
        Map<String, String> attributes
) {
}