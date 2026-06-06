# One record per crawl run; history is preserved across re-crawls
resource "aws_dynamodb_table" "crawl_jobs" {
  name         = var.jobs_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "jobId"

  attribute {
    name = "jobId"
    type = "S"
  }

  attribute {
    name = "url"
    type = "S"
  }

  attribute {
    name = "createdAt"
    type = "S"
  }

  # Enables per-URL history queries without a full table scan
  global_secondary_index {
    name            = "url-createdAt-index"
    hash_key        = "url"
    range_key       = "createdAt"
    projection_type = "ALL"
  }
}

# Canonical latest state per URL; overwritten on each successful crawl
resource "aws_dynamodb_table" "crawled_sites" {
  name         = var.sites_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "url"

  attribute {
    name = "url"
    type = "S"
  }
}
