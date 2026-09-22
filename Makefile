# launchpad-axi — build/test/lint/install. The distributable is a single-file zipapp
# (dist/launchpad-axi.pyz): stdlib-only, runs on any Python 3.10+, no install.
.PHONY: build install test lint clean vendor-axi

DIST := dist
BIN  := $(HOME)/.local/bin/launchpad-axi

# Output helpers and exit codes are vendored from craig-ai-tooling/axi-py (launchpad_axi/axi.py).
# Never edit that file here: change axi-py, tag it, then `make vendor-axi AXI_PY_REF=<tag>`.
AXI_PY_REF ?= v0.1.0

vendor-axi:
	@rm -rf build/axi-py
	git -c advice.detachedHead=false clone -q --depth 1 --branch $(AXI_PY_REF) https://github.com/craig-ai-tooling/axi-py build/axi-py
	python3 build/axi-py/vendor.py . launchpad_axi
	@rm -rf build/axi-py

build:
	@rm -rf build/stage $(DIST)
	@mkdir -p build/stage $(DIST)
	@cp -r launchpad_axi build/stage/
	python3 -m zipapp build/stage -m "launchpad_axi.cli:main" -o $(DIST)/launchpad-axi.pyz -p "/usr/bin/env python3"
	@rm -rf build/stage
	@echo "built $(DIST)/launchpad-axi.pyz"

install: build
	@mkdir -p $(dir $(BIN))
	@cp $(DIST)/launchpad-axi.pyz $(BIN)
	@chmod +x $(BIN)
	@echo "installed $(BIN)"

test:
	python3 -m unittest discover -s tests

lint:
	ruff check .

clean:
	rm -rf $(DIST) build
