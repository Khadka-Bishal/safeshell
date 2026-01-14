.PHONY: install test lint format clean build publish

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --cov=src/safeshell --cov-report=term-missing

lint:
	ruff check src/safeshell/
	mypy src/safeshell/ --ignore-missing-imports

format:
	ruff format src/safeshell/
	ruff check src/safeshell/ --fix

clean:
	rm -rf dist site .mypy_cache .pytest_cache .ruff_cache .coverage coverage.xml
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +

build: clean
	python3 -m build

publish: build
	twine upload dist/*


