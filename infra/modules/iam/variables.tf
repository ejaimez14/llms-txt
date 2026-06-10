variable "role_name" {
  description = "Name of the IAM role shared by Lambda and ECS Fargate tasks."
  type        = string
  default     = "llms-txt-app-role"
}

variable "aws_region" {
  description = "AWS region where resources are deployed."
  type        = string
}
