variable "api_gateway_endpoint" {
  description = "API Gateway invoke URL (from module.api_gateway output)"
  type        = string
}

variable "basic_auth_user" {
  description = "Username for CloudFront basic auth"
  type        = string
  default     = "demo"
}

variable "basic_auth_password" {
  sensitive   = true
  description = "Password for CloudFront basic auth"
  type        = string
}
