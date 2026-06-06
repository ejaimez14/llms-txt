output "anthropic_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the Anthropic API key. Referenced by the Lambda IAM policy in Phase 5."
  value       = aws_secretsmanager_secret.anthropic_key.arn
}
