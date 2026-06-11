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

variable "implement_task_family" {
  description = "ECS task definition family name for the implement agent (no ANTHROPIC_API_KEY; uses CLAUDE_CODE_OAUTH_TOKEN)"
}

variable "frontend_bucket_name" {
  description = "S3 bucket serving the frontend — implement agent publishes UI previews under experimental/<jobId>/"
}

variable "cloudfront_url" {
  description = "Public CloudFront URL used to build the experimental preview link returned by the implement agent"
}
