.PHONY: format lint test run build tf-plan tf-apply

format:
	uv run ruff format src/ tests/

lint:
	uv run ruff check --fix src/ tests/

test:
	uv run pytest tests/ -v

run:
	uv run uvicorn src.handler:app --reload --port 8000

build:
	bash build.sh

tf-plan:
	cd infra && terraform plan

tf-apply:
	cd infra && terraform apply
