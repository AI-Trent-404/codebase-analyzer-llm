.PHONY: install clone dry-run analyze test schema clean

install:
	pip install -r requirements.txt

clone:
	bash scripts/clone_target.sh

dry-run: clone
	python -m code_analyzer analyze --repo target-repo --dry-run --out out/analysis.dryrun.json

analyze: clone
	python -m code_analyzer analyze --repo target-repo --out out/analysis.json

test:
	pytest

schema:
	python -m code_analyzer schema --out out/output.schema.json

clean:
	rm -rf out .analyzer_cache target-repo .pytest_cache
