.PHONY: setup format lint test run build tf-init tf-plan tf-apply docker-login docker-push local-task

-include .env
export

# Defaults for local-task — override on the command line as needed.
AGENT_URL ?= https://anthropic.com
AGENT_MODEL ?= claude
AGENT_TYPE ?= crawl

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

# Run a single agent task locally (no Docker) against real AWS.
# Creates a fresh DynamoDB job record, then executes the task module directly.
# Use this to validate task logic before building and pushing the Docker image.
#
#   make local-task                                              # claude crawl of anthropic.com
#   make local-task AGENT_URL=https://example.com AGENT_TYPE=crawl AGENT_MODEL=openai
local-task:
	$(eval AGENT_ID := $(shell PYTHONPATH=. AWS_DEFAULT_REGION=us-east-1 uv run python scripts/create_test_job.py $(AGENT_URL) $(AGENT_MODEL)))
	@echo "Running $(AGENT_TYPE) task locally — job=$(AGENT_ID) url=$(AGENT_URL) model=$(AGENT_MODEL)"
	AGENT_ID=$(AGENT_ID) AGENT_URL=$(AGENT_URL) AGENT_MODEL=$(AGENT_MODEL) AGENT_TYPE=$(AGENT_TYPE) uv run python -m src.tasks
