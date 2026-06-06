variable "anthropic_api_key" {
  description = "Anthropic API key to store in Secrets Manager. The application fetches it by secret name at runtime."
  type        = string
  sensitive   = true
}
