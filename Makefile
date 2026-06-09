.PHONY: setup format lint test run build tf-init tf-plan tf-apply docker-login docker-push

-include .env
export

setup:
	uv venv --clear
	uv sync

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

tf-init:
	cd infra && terraform init

tf-plan: tf-init
	cd infra && terraform plan

tf-apply: tf-init
	cd infra && terraform apply

docker-login:
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(ECR_URL)

docker-push: docker-login
	docker build -f Dockerfile.agent -t $(ECR_URL):latest .
	docker push $(ECR_URL):latest
