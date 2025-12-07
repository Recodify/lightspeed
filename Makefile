PYTHON    ?= python3
VENV_DIR  ?= .venv
ACTIVATE  = ./activate.sh

.PHONY: all venv install dev test lint fmt clean dist

all: install

$(VENV_DIR)/bin/python:
	$(PYTHON) -m venv $(VENV_DIR)

venv: $(VENV_DIR)/bin/python

install: venv
	$(ACTIVATE) pip install --upgrade pip
	$(ACTIVATE) pip install -e .

dev: venv
	$(ACTIVATE) pip install --upgrade pip
	$(ACTIVATE) pip install -e ".[dev]"

test: venv
	$(ACTIVATE) pytest

lint: venv
	$(ACTIVATE) ruff check .

fmt: venv
	$(ACTIVATE) ruff check . --fix
	$(ACTIVATE) black .

dist: venv
	$(ACTIVATE) python -m build

clean:
	rm -rf $(VENV_DIR) *.egg-info .pytest_cache build dist
	find . -name '__pycache__' -type d -exec rm -rf {} +