SHELL := /usr/bin/env bash
.DEFAULT_GOAL := help
ARGS ?=

.PHONY: help sync clean lint format test \
	data data-agricultura data-inegi data-edafologia data-uso-suelo \
	data-avance data-agroprograma data-mapbiomas \
	features train predict run

#################################################################################
# COMMANDS                                                                 #
#################################################################################

## Show available commands
help:
	@awk '/^## / {desc = substr($$0, 4)} /^[a-zA-Z_-]+:/ {if (desc != "") {printf "%-25s %s\n", $$1, desc; desc = ""}}' $(MAKEFILE_LIST)

## Sync dependencies from uv.lock
sync:
	uv sync

## Remove caches
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d \( -name ".pytest_cache" -o -name ".ruff_cache" -o -name ".mypy_cache" \) -exec rm -rf {} +

## Lint with ruff
lint:
	uv run ruff check src
	uv run ruff format --check src

## Format with ruff
format:
	uv run ruff check --fix src
	uv run ruff format src

## Run tests
test:
	uv run pytest

#################################################################################
# DATA                                                                          #
#################################################################################

## Core downloads: agricultura + inegi + edafologia
data: data-agricultura data-inegi data-edafologia
	@echo "Descarga core terminada"

## Download DGSIAP agricultural data + dictionary
data-agricultura:
	uv run python -m proyecto_agronomia.dataset agricultura

## Download INEGI municipal/state geometries
data-inegi:
	uv run python -m proyecto_agronomia.dataset inegi

## Download INEGI edafology data + dictionary
data-edafologia:
	uv run python -m proyecto_agronomia.dataset edafologia

## Download INEGI land use/vegetation series
data-uso-suelo:
	uv run python -m proyecto_agronomia.dataset inegi-uso-suelo

## Download DGSIAP crop progress report
data-avance:
	uv run python -m proyecto_agronomia.dataset dgsiap-avance

## Download DGSIAP AgroPrograma intention report
data-agroprograma:
	uv run python -m proyecto_agronomia.dataset dgsiap-agroprograma

## Process MapBiomas rasters to agricultural coverage
data-mapbiomas:
	uv run python -m proyecto_agronomia.dataset mapbiomas-procesar

#################################################################################
# FEATURES                                                                      #
#################################################################################

## Build processed agricultural features dataset
features:
	uv run python -m proyecto_agronomia.features

#################################################################################
# MODELING                                                                      #
#################################################################################

## Train and register a crop model (ARGS="--cultivo ...")
train:
	uv run python -m modeling.train $(ARGS)

## Run model inference (ARGS="...")
predict:
	uv run python -m modeling.predict $(ARGS)

## Run arbitrary command in project env: make run cmd="..."
run:
	uv run $(cmd)
