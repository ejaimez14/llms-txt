variable "aws_region" {
  description = "AWS region where all resources are deployed."
  default     = "us-east-1"
}

variable "lambda_zip_path" {
  description = "Path to the Lambda deployment zip artifact built by build.sh."
  type        = string
  default     = "../lambda.zip"
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

variable "basic_auth_user" {
  description = "Username for CloudFront basic auth"
  type        = string
  default     = "demo"
}

variable "basic_auth_password" {
  sensitive   = true
  description = "Password for CloudFront basic auth — share with interviewers"
  type        = string
}
