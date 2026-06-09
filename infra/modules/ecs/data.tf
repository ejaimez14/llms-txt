data "aws_secretsmanager_secret" "anthropic" {
  name = "secrets/anthropic-api-key"
}

data "aws_secretsmanager_secret" "pinecone" {
  name = "secrets/pinecone-api-key"
}

data "aws_secretsmanager_secret" "github" {
  name = "secrets/github-token"
}

data "aws_secretsmanager_secret" "openai" {
  name = "secrets/openai-api-key"
}
