module "s3" {
  source      = "./modules/s3"
  bucket_name = "crawler-output"
}

module "dynamodb" {
  source           = "./modules/dynamodb"
  jobs_table_name  = "crawler-jobs"
  sites_table_name = "crawler-sites"
}

