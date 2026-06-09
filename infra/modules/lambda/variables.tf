variable "iam_role_arn" {
  description = "ARN of the existing IAM role used by the Lambda function."
  type        = string
}

variable "lambda_zip_path" {
  description = "Path to the Lambda deployment zip artifact."
  type        = string
}

variable "bucket_name" {
  description = "Name of the S3 bucket the Lambda function reads and writes results to."
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

variable "pinecone_index" {
  description = "Name of the Pinecone index used for embedding storage and retrieval."
  type        = string
}

variable "ecs_cluster" {
  description = "Name of the ECS cluster used to run Fargate agent tasks."
  type        = string
}

variable "ecs_task_definition" {
  description = "ARN of the shared ECS task definition used by all agent tasks."
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

variable "recrawl_queue_url" {
  description = "URL of the SQS re-crawl queue — passed to Lambda as RECRAWL_QUEUE_URL."
  type        = string
}
