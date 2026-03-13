package com.pedrolucas.lab.service;

import com.pedrolucas.lab.dto.TransformRequest;
import com.pedrolucas.lab.dto.TransformResponse;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

@ApplicationScoped
public class TransformService {

    public TransformResponse transform(TransformRequest request) {
        List<String> normalizedItems = new ArrayList<>();
        for (String item : request.items()) {
            normalizedItems.add(normalize(item));
        }

        Map<String, String> normalizedMetadata = new HashMap<>();
        for (Map.Entry<String, String> entry : request.metadata().entrySet()) {
            normalizedMetadata.put(
                    normalize(entry.getKey()),
                    normalize(entry.getValue())
            );
        }

        String normalizedCustomerName = normalize(request.customerName());

        boolean valid = request.requestId() != null
                && !request.requestId().isBlank()
                && normalizedCustomerName != null
                && !normalizedCustomerName.isBlank();

        return new TransformResponse(
                request.requestId(),
                normalizedCustomerName,
                normalizedItems.size(),
                normalizedItems,
                normalizedMetadata,
                valid
        );
    }

    private String normalize(String value) {
        if (value == null) {
            return "";
        }

        return value.strip().toLowerCase(Locale.ROOT);
    }
}