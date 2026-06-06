variable "aws_region" {
  description = "AWS region where all resources are deployed."
  default     = "us-east-1"
}

variable "anthropic_api_key" {
  description = "Anthropic API key — written to Secrets Manager, never used directly by Lambda."
  sensitive   = true
}
