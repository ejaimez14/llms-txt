variable "aws_region" {
  description = "AWS region where all resources are deployed."
  default     = "us-east-1"
}

variable "iam_role_arn" {
  description = "ARN of the existing IAM role used across all compute resources"
}

variable "lambda_zip_path" {
  description = "Path to the Lambda deployment zip artifact built by build.sh."
  type        = string
}

variable "pinecone_api_key" {
  description = "Pinecone API key injected into the Lambda environment."
  type        = string
  sensitive   = true
}

variable "pinecone_index" {
  description = "Name of the Pinecone index used for embedding storage and retrieval"
}

variable "anthropic_secret_arn" {
  description = "Secrets Manager ARN for the Anthropic API key"
}

variable "github_secret_arn" {
  description = "Secrets Manager ARN for the GitHub personal access token"
  sensitive   = true
}

variable "pinecone_secret_arn" {
  description = "Secrets Manager ARN for the Pinecone API key"
}

variable "vpc_id" {
  description = "VPC ID in which Fargate tasks run"
}

variable "subnet_ids" {
  description = "Comma-separated subnet IDs for Fargate task networking"
}
