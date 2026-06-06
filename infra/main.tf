terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "s3" {
  source      = "./modules/s3"
  bucket_name = "crawler-output"
}

module "dynamodb" {
  source           = "./modules/dynamodb"
  jobs_table_name  = "crawler-jobs"
  sites_table_name = "crawler-sites"
}

module "secrets" {
  source            = "./modules/secrets"
  anthropic_api_key = var.anthropic_api_key
}
