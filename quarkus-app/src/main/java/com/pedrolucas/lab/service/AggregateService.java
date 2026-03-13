package com.pedrolucas.lab.service;

import com.pedrolucas.lab.dto.AggregateResponse;
import jakarta.enterprise.context.ApplicationScoped;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@ApplicationScoped
public class AggregateService {

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

        List<Callable<String>> tasks = List.of(
                () -> simulateIoTask("io-task-1", 25),
                () -> simulateIoTask("io-task-2", 40),
                () -> simulateCpuTask("cpu-task-1", 50_000),
                () -> simulateTransformTask("transform-task-1")
        );

        List<String> completed = new ArrayList<>();

        try {
            executor.invokeAll(tasks).forEach(future -> {
                try {
                    completed.add(future.get());
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    completed.add("interrupted");
                } catch (ExecutionException e) {
                    completed.add("failed:" + e.getClass().getSimpleName());
                }
            });
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            completed.add("batch-interrupted");
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

    private String simulateIoTask(String name, long sleepMs) throws InterruptedException {
        Thread.sleep(sleepMs);
        return name + "-done";
    }

    private String simulateCpuTask(String name, int iterations) {
        long acc = 0;
        for (int i = 0; i < iterations; i++) {
            acc += (long) i * (i % 7);
        }
        return name + "-done-" + acc;
    }

    private String simulateTransformTask(String name) {
        List<String> values = List.of(" Alpha ", "Beta ", " GAMMA ", " delta ");
        List<String> normalized = new ArrayList<>(values.size());

        for (String value : values) {
            normalized.add(value.strip().toLowerCase());
        }

        return name + "-done-" + normalized.size();
    }
}