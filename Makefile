PYTHON      = python3
PIPELINE    = test_full_pipeline.py
RUNNER      = run_tests.py
SAMPLES     = samples

.PHONY: all install demo opt test test-all test-verbose test-strict smoke run one list cfg check clean help

all: demo

install:
	$(PYTHON) -m pip install ply astropy numpy pandas

demo:
	$(PYTHON) $(PIPELINE) $(SAMPLES)/demo.lumen

opt:
	$(PYTHON) $(PIPELINE) $(SAMPLES)/demo_o.lumen

run:
	$(PYTHON) $(PIPELINE) $(FILE)

one:
	$(PYTHON) $(PIPELINE) $(SAMPLES)/test$(N).lumen

test:
	$(PYTHON) $(RUNNER) $(SAMPLES)/ --filter test

test-all:
	$(PYTHON) $(RUNNER) $(SAMPLES)/

test-verbose:
	$(PYTHON) $(RUNNER) $(SAMPLES)/ --filter test --verbose

test-strict:
	$(PYTHON) $(RUNNER) $(SAMPLES)/ --filter test --stop-on-fail

smoke:
	$(PYTHON) $(PIPELINE) $(SAMPLES)/demo.lumen
	$(PYTHON) $(RUNNER) $(SAMPLES)/ --filter test0

list:
	@ls $(SAMPLES)/*.lumen 2>/dev/null | sort

cfg:
	@for f in $(SAMPLES)/*.dot; do \
		[ -f "$$f" ] || continue; \
		dot -Tpng "$$f" -o "$${f%.dot}.png"; \
		echo "Rendered $${f%.dot}.png"; \
	done

check:
	@$(PYTHON) --version
	@$(PYTHON) -m pip show ply astropy numpy pandas 2>/dev/null | grep -E "^(Name|Version):" | paste - -

clean:
	@rm -f parsetab.py parser.out lextab.py
	@rm -f $(SAMPLES)/*.dot $(SAMPLES)/*.png
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned."

help:
	@echo ""
	@echo "  Lumen Compiler - Makefile targets"
	@echo ""
	@echo "  Setup"
	@echo "    make install            Install ply astropy numpy pandas"
	@echo "    make check              Show Python and package versions"
	@echo ""
	@echo "  Demos"
	@echo "    make demo               Run samples/demo.lumen"
	@echo "    make opt                Run samples/demo_o.lumen"
	@echo "    make run FILE=f.lumen   Run any specific file"
	@echo "    make one N=20           Run samples/test20.lumen"
	@echo ""
	@echo "  Testing"
	@echo "    make test               Run all testX.lumen files"
	@echo "    make test-all           Run every .lumen file"
	@echo "    make test-verbose       Run tests with full output"
	@echo "    make test-strict        Stop on first failure"
	@echo "    make smoke              Run demo plus test01-test09"
	@echo "    make list               List all .lumen files"
	@echo ""
	@echo "  Cleanup"
	@echo "    make clean              Remove cache and generated files"
	@echo "    make cfg                Render CFG dot files to PNG"
	@echo ""
