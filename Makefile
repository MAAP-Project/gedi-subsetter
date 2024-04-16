CONDA_EXE ?= conda
CONDA_ENV_NAME = gedi_subset
CONDA_PREFIX = $(shell $(CONDA_EXE) info --base)/envs/$(CONDA_ENV_NAME)
# NOTE: The python version is hard-coded here.  If the python version changes,
#       this will need to be updated.
MAAP = $(CONDA_PREFIX)/lib/python3.11/site-packages/maap

.DEFAULT_GOAL := help

.PHONY: help lock build clean test lint check

help: Makefile
	@echo
	@echo "Usage: make [options] target ..."
	@echo
	@echo "Run 'make -h' to list available options."
	@echo
	@echo "Available targets:"
	@echo
	@sed -n 's/^##//p' $< | column -t -s ':' | sed -e 's/^/ /'
	@echo

printenv:
	printenv | sort
	exit 1

# NOTE: This will fail if the conda environment does not exist.  Run `make build`.
conda-lock.yml: environment.yml environment-dev.yml bin/lock
	@bin/lock

$(CONDA_PREFIX): bin/create
	@bin/create

$(MAAP): $(CONDA_PREFIX) conda-lock.yml bin/install
	@bin/install

## lock: generate the lock file (conda-lock.yml) for the gedi_subset environment
# Simply a convenience target to generate the lock file since typing `make lock`
# is easier than typing `make conda-lock.yml` (if not using tab completion).
# NOTE: This will fail if the conda environment does not exist.  Run `make build`.
lock: conda-lock.yml

## build: build the gedi_subset environment with dependencies from conda-lock.yml
build: $(MAAP)

## clean: remove the gedi_subset Jupyter kernel and gedi_subset environment
clean:
	@bin/clean

## test: run unit tests
test:
	@bin/run pytest -v --record-mode=once

## lint: run file/code linters
lint:
	@bin/run pre-commit run -a

## typecheck: run the type checker against the codebase
typecheck:
	@bin/run mypy src tests typings
