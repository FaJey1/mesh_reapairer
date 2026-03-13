.PHONY: fmt lint typecheck test build build-bin all

fmt:
	uv run ruff format .

lint:
	uv run ruff check .

typecheck:
	uv run mypy .

test:
	uv run pytest

build:
	uv build

build-bin:
	uv run pyinstaller --onefile --name mesh-reapairer scripts/mesh_reapairer_entry.py

all: fmt lint typecheck test

