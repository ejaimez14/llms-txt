output "bucket_name" {
  description = "The actual name of the S3 bucket (base name + random suffix)."
  value       = aws_s3_bucket.crawler_results.bucket
}

output "bucket_arn" {
  description = "ARN of the S3 bucket, used by IAM policies in later phases."
  value       = aws_s3_bucket.crawler_results.arn
}
