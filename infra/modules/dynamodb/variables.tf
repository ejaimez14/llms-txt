variable "jobs_table_name" {
  description = "Name of the DynamoDB table that stores crawl job history (one record per invocation)."
  type        = string
}

variable "sites_table_name" {
  description = "Name of the DynamoDB table that stores the latest successful crawl state per URL."
  type        = string
}
