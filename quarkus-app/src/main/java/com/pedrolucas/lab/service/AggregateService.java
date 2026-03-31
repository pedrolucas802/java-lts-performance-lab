package com.pedrolucas.lab.service;

import com.pedrolucas.lab.dto.AggregateResponse;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.ws.rs.WebApplicationException;
import jakarta.ws.rs.core.Response;

import java.math.BigDecimal;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@ApplicationScoped
public class AggregateService {

    private static final long DATASET_MAX_ID = 50_000;

    private static final String COUNT_SQL = """
            SELECT COUNT(*)
            FROM benchmark_products
            WHERE id BETWEEN ? AND ?
            """;
    private static final String AVG_PRICE_SQL = """
            SELECT ROUND(AVG(price), 2)
            FROM benchmark_products
            WHERE id BETWEEN ? AND ?
            """;
    private static final String DISTINCT_BRANDS_SQL = """
            SELECT COUNT(DISTINCT brand)
            FROM benchmark_products
            WHERE id BETWEEN ? AND ?
            """;
    private static final String SAMPLE_NAME_SQL = """
            SELECT name
            FROM benchmark_products
            WHERE id BETWEEN ? AND ?
            ORDER BY id
            LIMIT 1
            """;

    @Inject
    BenchmarkDataSourceService dataSourceService;

    public AggregateResponse runPlatformTasks() {
        ExecutorService executor = Executors.newFixedThreadPool(4);
        try {
            return runTasks("platform", executor);
        } finally {
            executor.shutdown();
        }
    }

    public AggregateResponse runVirtualTasks() {
        ExecutorService executor = createVirtualThreadExecutorIfAvailable();

        if (executor == null) {
            return new AggregateResponse(
                    "virtual-unsupported",
                    UUID.randomUUID().toString(),
                    List.of("virtual-threads-not-supported-on-this-java-version"),
                    0,
                    0
            );
        }

        try {
            return runTasks("virtual", executor);
        } finally {
            executor.shutdown();
        }
    }

    private ExecutorService createVirtualThreadExecutorIfAvailable() {
        try {
            Method method = Executors.class.getMethod("newVirtualThreadPerTaskExecutor");
            Object result = method.invoke(null);
            return (ExecutorService) result;
        } catch (NoSuchMethodException | IllegalAccessException | InvocationTargetException e) {
            return null;
        }
    }

    private AggregateResponse runTasks(String mode, ExecutorService executor) {
        long start = System.nanoTime();
        String requestId = UUID.randomUUID().toString();
        dataSourceService.requireConfigured();

        List<Callable<String>> tasks = List.of(
                () -> runJdbcAggregateTask("jdbc-slice-a", 1, 12_500),
                () -> runJdbcAggregateTask("jdbc-slice-b", 12_501, 25_000),
                () -> runJdbcAggregateTask("jdbc-slice-c", 25_001, 37_500),
                () -> runJdbcAggregateTask("jdbc-slice-d", 37_501, DATASET_MAX_ID)
        );

        List<String> completed = new ArrayList<>();

        try {
            executor.invokeAll(tasks).forEach(future -> completed.add(awaitTaskResult(future)));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new WebApplicationException(
                    "Aggregate benchmark interrupted.",
                    e,
                    Response.Status.INTERNAL_SERVER_ERROR
            );
        }

        long elapsedMs = (System.nanoTime() - start) / 1_000_000;

        return new AggregateResponse(
                mode,
                requestId,
                completed,
                completed.size(),
                elapsedMs
        );
    }

    private String awaitTaskResult(java.util.concurrent.Future<String> future) {
        try {
            return future.get();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new WebApplicationException(
                    "Aggregate benchmark interrupted while awaiting task results.",
                    e,
                    Response.Status.INTERNAL_SERVER_ERROR
            );
        } catch (ExecutionException e) {
            Throwable cause = e.getCause();
            if (cause instanceof RuntimeException runtimeException) {
                throw runtimeException;
            }
            throw new WebApplicationException(
                    "Aggregate benchmark task failed.",
                    cause,
                    Response.Status.INTERNAL_SERVER_ERROR
            );
        }
    }

    private String runJdbcAggregateTask(String name, long startId, long endId) throws SQLException {
        try (Connection connection = dataSourceService.getConnection()) {
            long count = queryCount(connection, startId, endId);
            BigDecimal averagePrice = queryAveragePrice(connection, startId, endId);
            int distinctBrands = queryDistinctBrands(connection, startId, endId);
            String sampleName = querySampleName(connection, startId, endId);

            return name
                    + "-done-count" + count
                    + "-avg" + formatDecimal(averagePrice)
                    + "-brands" + distinctBrands
                    + "-sample" + sampleName;
        }
    }

    private long queryCount(Connection connection, long startId, long endId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(COUNT_SQL)) {
            bindRange(statement, startId, endId);
            try (ResultSet resultSet = statement.executeQuery()) {
                resultSet.next();
                return resultSet.getLong(1);
            }
        }
    }

    private BigDecimal queryAveragePrice(Connection connection, long startId, long endId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(AVG_PRICE_SQL)) {
            bindRange(statement, startId, endId);
            try (ResultSet resultSet = statement.executeQuery()) {
                resultSet.next();
                return resultSet.getBigDecimal(1);
            }
        }
    }

    private int queryDistinctBrands(Connection connection, long startId, long endId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(DISTINCT_BRANDS_SQL)) {
            bindRange(statement, startId, endId);
            try (ResultSet resultSet = statement.executeQuery()) {
                resultSet.next();
                return resultSet.getInt(1);
            }
        }
    }

    private String querySampleName(Connection connection, long startId, long endId) throws SQLException {
        try (PreparedStatement statement = connection.prepareStatement(SAMPLE_NAME_SQL)) {
            bindRange(statement, startId, endId);
            try (ResultSet resultSet = statement.executeQuery()) {
                if (resultSet.next()) {
                    return resultSet.getString(1);
                }
                return "none";
            }
        }
    }

    private void bindRange(PreparedStatement statement, long startId, long endId) throws SQLException {
        statement.setLong(1, startId);
        statement.setLong(2, endId);
    }

    private String formatDecimal(BigDecimal value) {
        if (value == null) {
            return "0";
        }
        return value.stripTrailingZeros().toPlainString();
    }
}
