package com.pedrolucas.benchmarks.json;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.pedrolucas.benchmarks.common.BenchmarkConstants;
import com.pedrolucas.benchmarks.common.SampleDataFactory;
import com.pedrolucas.benchmarks.common.SampleProduct;
import org.openjdk.jmh.annotations.Benchmark;
import org.openjdk.jmh.annotations.BenchmarkMode;
import org.openjdk.jmh.annotations.Fork;
import org.openjdk.jmh.annotations.Level;
import org.openjdk.jmh.annotations.Measurement;
import org.openjdk.jmh.annotations.Mode;
import org.openjdk.jmh.annotations.OutputTimeUnit;
import org.openjdk.jmh.annotations.Scope;
import org.openjdk.jmh.annotations.Setup;
import org.openjdk.jmh.annotations.State;
import org.openjdk.jmh.annotations.Warmup;

import java.util.List;
import java.util.concurrent.TimeUnit;

@BenchmarkMode(Mode.Throughput)
@OutputTimeUnit(TimeUnit.SECONDS)
@Warmup(iterations = 2, time = 2)
@Measurement(iterations = 3, time = 3)
@Fork(1)
public class JsonSerializationBenchmark {

    @State(Scope.Thread)
    public static class BenchmarkState {
        ObjectMapper objectMapper;
        List<SampleProduct> smallProducts;
        List<SampleProduct> mediumProducts;

        @Setup(Level.Trial)
        public void setup() {
            objectMapper = new ObjectMapper();
            smallProducts = SampleDataFactory.createProducts(BenchmarkConstants.SMALL_SIZE);
            mediumProducts = SampleDataFactory.createProducts(BenchmarkConstants.MEDIUM_SIZE);
        }
    }

    @Benchmark
    public String serializeSmallList(BenchmarkState state) throws JsonProcessingException {
        return state.objectMapper.writeValueAsString(state.smallProducts);
    }

    @Benchmark
    public String serializeMediumList(BenchmarkState state) throws JsonProcessingException {
        return state.objectMapper.writeValueAsString(state.mediumProducts);
    }
}