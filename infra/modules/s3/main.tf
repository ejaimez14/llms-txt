resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "crawler_results" {
  bucket = "${var.bucket_name}-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket_public_access_block" "crawler_results" {
  bucket = aws_s3_bucket.crawler_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
