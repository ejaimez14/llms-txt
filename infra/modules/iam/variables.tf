variable "role_name" {
  description = "Name of the IAM role shared by Lambda and ECS Fargate tasks."
  type        = string
  default     = "llms-txt-app-role"
}

variable "create_ecs_service_linked_role" {
  description = "Set to false if AWSServiceRoleForECS already exists in the account (created by prior ECS usage). Defaults to true."
  type        = bool
  default     = true
}
