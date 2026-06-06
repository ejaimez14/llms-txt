resource "aws_secretsmanager_secret" "anthropic_api_key" {
  name = "llms-txt/anthropic-api-key"
}

resource "aws_secretsmanager_secret_version" "anthropic_api_key" {
  secret_id     = aws_secretsmanager_secret.anthropic_api_key.id
  secret_string = jsonencode({ value = var.anthropic_api_key })
}
