variable "iam_role_arn" {
  description = "ARN of the existing IAM role used by the Lambda function."
  type        = string
}

variable "lambda_zip_path" {
  description = "Path to the Lambda deployment zip artifact."
  type        = string
}

variable "bucket_name" {
  description = "Name of the S3 bucket the Lambda function reads and writes crawler results to."
  type        = string
}

variable "table_name" {
  description = "Name of the DynamoDB jobs table."
  type        = string
}

variable "sites_table_name" {
  description = "Name of the DynamoDB sites table."
  type        = string
}

variable "pinecone_api_key" {
  description = "Pinecone API key injected into the Lambda environment."
  type        = string
  sensitive   = true
}

variable "pinecone_index" {
  description = "Name of the Pinecone index used for embedding storage and retrieval."
  type        = string
}

variable "ecs_cluster" {
  description = "Name of the ECS cluster used to run Fargate agent tasks."
  type        = string
}

variable "ecs_implementer_task_definition" {
  description = "ARN of the ECS task definition for the UI implementer agent."
  type        = string
}

variable "ecs_crawler_task_definition" {
  description = "ARN of the ECS task definition for the crawler agent."
  type        = string
}

variable "ecs_ui_planner_task_definition" {
  description = "ARN of the ECS task definition for the UI planner agent."
  type        = string
}

variable "ecs_security_group" {
  description = "Security group ID attached to Fargate tasks."
  type        = string
}

variable "ecs_subnet_ids" {
  description = "Comma-separated subnet IDs for Fargate task networking."
  type        = string
}
