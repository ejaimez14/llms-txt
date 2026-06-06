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
