variable "lambda_function_name" {
  description = "Name of the crawler Lambda function, used to scope CloudWatch metric widgets."
  type        = string
}

variable "api_gateway_id" {
  description = "ID of the HTTP API Gateway, used to scope API Gateway metric widgets."
  type        = string
}

variable "ecs_log_group_name" {
  description = "CloudWatch log group name for ECS Fargate task logs"
  type        = string
}
