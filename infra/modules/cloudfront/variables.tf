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

variable "control_room_ui_bucket_name" {
  description = "Name of the control-room static UI S3 bucket (created by the agent-org-platform deploy)"
  type        = string
}
