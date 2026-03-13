package com.pedrolucas.lab.dto;

import java.util.List;
import java.util.Map;

public record TransformRequest(
        String requestId,
        String customerName,
        List<String> items,
        Map<String, String> metadata
) {
}