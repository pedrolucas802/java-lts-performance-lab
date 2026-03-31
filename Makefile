.PHONY: help jmh startup concurrency gc charts clean aggregate full-lab

JAVA_VERSION ?= 21
LANE ?=
INCLUDE_MIXED ?= false

help:
	@echo "Available targets:"
	@echo "  make jmh"
	@echo "  make startup"
	@echo "  make concurrency"
	@echo "  make gc"
	@echo "  make aggregate"
	@echo "  make charts"
	@echo "  make full-lab"
	@echo "  make clean"
	@echo ""
	@echo "Variables:"
	@echo "  JAVA_VERSION=21"
	@echo "  LANE=macos-container|linux-container"
	@echo "  INCLUDE_MIXED=true|false"

jmh:
	bash scripts/runners/run_jmh_suite.sh $(JAVA_VERSION)

startup:
	bash scripts/runners/run_quarkus_startup_benchmark.sh $(JAVA_VERSION) 3

concurrency:
	bash scripts/runners/run_concurrency_study.sh $(JAVA_VERSION) 20s 2,10,25,50

gc:
	bash scripts/runners/run_gc_suite.sh $(JAVA_VERSION) 20s 10

charts:
	python3 scripts/charts/generate_startup_chart.py
	python3 scripts/charts/generate_quarkus_charts.py
	python3 scripts/charts/generate_concurrency_charts.py
	python3 scripts/charts/generate_gc_charts.py
	python3 scripts/charts/generate_cpu_charts.py

clean:
	find . -name target -type d -exec rm -rf {} +

aggregate:
	python3 scripts/aggregators/aggregate_startup_results.py
	python3 scripts/aggregators/aggregate_quarkus_results.py
	python3 scripts/aggregators/aggregate_concurrency_results.py
	python3 scripts/aggregators/aggregate_memory_results.py
	python3 scripts/aggregators/aggregate_gc_results.py
	python3 scripts/aggregators/aggregate_cpu_results.py
	python3 scripts/aggregators/aggregate_jfr_results.py

full-lab:
	python3 scripts/runners/run_full_benchmark_lab.py --versions 17 21 25 $(if $(LANE),--lane $(LANE),) $(if $(filter true,$(INCLUDE_MIXED)),--include-mixed-workload,)
