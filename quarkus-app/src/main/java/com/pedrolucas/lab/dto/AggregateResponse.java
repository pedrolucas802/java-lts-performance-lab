package com.pedrolucas.lab.dto;

import java.util.List;

public record AggregateResponse(
        String mode,
        String requestId,
        List<String> completedTasks,
        int totalTasks,
        long elapsedMs
) {
}