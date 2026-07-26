.PHONY: install test lint dashboard analyze

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

dashboard:
	streamlit run dashboard/app.py

analyze:
	python -m arblens data/sample_chain.csv
