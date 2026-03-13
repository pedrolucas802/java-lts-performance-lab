.PHONY: help jmh quarkus gc charts clean

JAVA_VERSION ?= 21

help:
	@echo "Available targets:"
	@echo "  make jmh"
	@echo "  make quarkus"
	@echo "  make gc"
	@echo "  make charts"
	@echo "  make clean"

jmh:
	mvn -pl jmh-benchmarks clean package -Djava.release=$(JAVA_VERSION)
	java -jar jmh-benchmarks/target/jmh-benchmarks.jar -rf json -rff results/raw/java$(JAVA_VERSION)/jmh/json-serialization-baseline.json

quarkus:
	./scripts/run_quarkus_startup_benchmark.sh $(JAVA_VERSION)

gc:
	@echo "GC benchmark suite not implemented yet."

charts:
	@echo "Chart generation not implemented yet."

clean:
	find . -name target -type d -exec rm -rf {} +

aggregate:
	python3 scripts/aggregate_quarkus_results.py