# launchpad-axi — build/test/lint. The distributable is a single-file zipapp
# (dist/launchpad-axi.pyz): stdlib-only, runs on any Python 3.10+, no install.
.PHONY: build test lint clean

DIST := dist

build:
	@rm -rf build/stage $(DIST)
	@mkdir -p build/stage $(DIST)
	@cp -r launchpad_axi build/stage/
	python3 -m zipapp build/stage -m "launchpad_axi.cli:main" -o $(DIST)/launchpad-axi.pyz -p "/usr/bin/env python3"
	@rm -rf build/stage
	@echo "built $(DIST)/launchpad-axi.pyz"

test:
	python3 -m unittest discover -s tests

lint:
	ruff check .

clean:
	rm -rf $(DIST) build
