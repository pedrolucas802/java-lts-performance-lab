.PHONY: help jmh quarkus gc charts clean

help:
	@echo "Available targets:"
	@echo "  make jmh"
	@echo "  make quarkus"
	@echo "  make gc"
	@echo "  make charts"
	@echo "  make clean"

jmh:
	@echo "JMH benchmark runner not implemented yet."

quarkus:
	@echo "Quarkus benchmark runner not implemented yet."

gc:
	@echo "GC benchmark suite not implemented yet."

charts:
	@echo "Chart generation not implemented yet."

clean:
	find . -name target -type d -exec rm -rf {} +

aggregate:
	python3 scripts/aggregate_quarkus_results.py