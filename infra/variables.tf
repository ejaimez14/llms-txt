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
  default     = "./lambda.zip"
}

variable "pinecone_index" {
  description = "Name of the Pinecone index used for embedding storage and retrieval"
}

variable "vpc_id" {
  description = "VPC ID in which Fargate tasks run"
}

variable "subnet_ids" {
  description = "Comma-separated subnet IDs for Fargate task networking"
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
