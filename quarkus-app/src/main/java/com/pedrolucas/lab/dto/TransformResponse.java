package com.pedrolucas.lab.dto;

import java.util.List;
import java.util.Map;

public record TransformResponse(
        String requestId,
        String normalizedCustomerName,
        int itemCount,
        List<String> normalizedItems,
        Map<String, String> normalizedMetadata,
        boolean valid
) {
}