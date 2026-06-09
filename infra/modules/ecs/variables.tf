variable "iam_role_arn" {
  description = "ARN of the existing IAM role used for both task execution and task role"
}

variable "ecr_repository_name" {
  description = "Name of the ECR repository shared by all Fargate agents"
}

variable "cluster_name" {
  description = "Name of the ECS cluster"
}

variable "task_family" {
  description = "ECS task definition family name shared by all agent tasks"
}

variable "task_cpu" {
  description = "vCPU units for Fargate tasks (1024 = 1 vCPU)"
  default     = 1024
}

variable "task_memory" {
  description = "Memory in MB for Fargate tasks"
  default     = 2048
}

variable "log_group_name" {
  description = "CloudWatch log group name for all Fargate task stdout/stderr"
}

variable "aws_region" {
  description = "AWS region for log configuration"
}

variable "bucket_name" {
  description = "S3 bucket name passed to containers as an environment variable"
}

variable "jobs_table_name" {
  description = "DynamoDB jobs table name"
}

variable "sites_table_name" {
  description = "DynamoDB sites table name"
}

variable "pinecone_index" {
  description = "Pinecone index name"
}

variable "vpc_id" {
  description = "VPC ID for the Fargate task security group"
}

variable "implementer_repo" {
  description = "GitHub repository the implementer agent clones and opens PRs against (e.g. https://github.com/org/repo)"
  type        = string
}

variable "implementer_base_branch" {
  description = "Base branch the implementer agent targets when opening PRs"
  type        = string
  default     = "main"
}
