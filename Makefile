# Makefile: single entry point for all automation.
# Every command CI runs must be runnable locally via `make <target>`.
# This prevents "works on my machine" drift between local and CI.

.PHONY: help install install-dev validate test lint format ci pre-commit-install \
        pass-a pass-b pass-c refresh build-site clean

help:
	@echo "Available targets:"
	@echo "  install            Install package"
	@echo "  install-dev        Install package with dev extras + pre-commit"
	@echo "  pre-commit-install Register git hooks for auto-validation on commit"
	@echo "  validate           Run taxonomy drift guard + adjacency integrity (fast)"
	@echo "  audit              Run Layer 1 content-quality audits"
	@echo "  benchmark          Run Layer 2 matcher benchmark against golden set"
	@echo "  test               Run full test suite"
	@echo "  lint               Run ruff"
	@echo "  format             Auto-fix formatting"
	@echo "  ci                 Run the same checks CI runs: validate + audit + test + lint"
	@echo "  pass-a             [Pass A] Type adjacent_to; enforce symmetry"
	@echo "  pass-b             [Pass B] Add disambiguation field"
	@echo "  pass-c             [Pass C] Tighten applies_when (not yet implemented)"
	@echo "  refresh            Weekly GPU-free refresh: citations + OA links over corpus.json"
	@echo "  build-site         Rebuild docs/risk_data.js from corpus.json"
	@echo "  clean              Remove caches"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pip install pre-commit
	$(MAKE) pre-commit-install

pre-commit-install:
	pre-commit install

# Fast structural check — runs in <1s, used as pre-commit hook and first CI step.
# If this fails, downstream tests are meaningless.
validate:
	pytest tests/test_adjacencies.py -v

# Layer 1 quality audits. Slightly slower than validate, still fast (<2s).
audit:
	pytest tests/test_quality_audits.py -v

# Layer 2 benchmark: run the baseline matcher against the golden set
# and report recall@K. Does not currently gate on a hard floor (the smoke
# tests in test_benchmark.py do that); this target is for human inspection.
benchmark:
	PYTHONPATH=src python -c "from ai_risk_retrieval.benchmark import KeywordOverlapMatcher, run_benchmark; m = KeywordOverlapMatcher.from_definitions(); print(run_benchmark(m).summary())"

test:
	pytest -v

lint:
	ruff check src tests

format:
	ruff check --fix src tests
	ruff format src tests

# The exact sequence CI runs. Run before pushing.
ci: validate audit test lint

# Pass A: idempotent — re-running on already-typed file leaves it typed.
# Now also enforces symmetry on similar edges.
pass-a:
	python scripts/pass_a_cleanup_and_type.py
	$(MAKE) validate

# Pass B: idempotent — adds disambiguation field. Content lives in
# scripts/disambiguation_content.py; the script derives reverse-direction
# disambigs automatically for symmetric edges.
pass-b:
	python scripts/pass_b_disambiguation.py
	$(MAKE) validate

pass-c:
	@echo "Pass C not yet implemented"
	@exit 1

# Weekly maintenance (no GPU, stdlib only): re-pull citation counts and OA links
# for the existing corpus, then rebuild the site data. Same commands CI runs in
# .github/workflows/weekly-refresh.yml — runnable locally for a manual refresh.
refresh:
	python scripts/refresh_corpus.py --corpus corpus.json
	$(MAKE) build-site

build-site:
	python build_data.py -i corpus.json -o docs/risk_data.js -e excerpts.json

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
