# Jobs table — full run history, one record per crawl invocation
resource "aws_dynamodb_table" "jobs" {
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

  # GSI for "give me all crawl runs for this URL, sorted by date"
  global_secondary_index {
    name            = "url-createdAt-index"
    hash_key        = "url"
    range_key       = "createdAt"
    projection_type = "ALL"
  }
}

# Sites table — one record per URL, always the latest successful crawl
resource "aws_dynamodb_table" "sites" {
  name         = var.sites_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "url"

  attribute {
    name = "url"
    type = "S"
  }
}
