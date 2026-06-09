output "cloudfront_url" {
  description = "Public HTTPS URL of the CloudFront distribution."
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "frontend_bucket_name" {
  description = "Name of the S3 bucket serving the frontend — upload index.html here."
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID — use to invalidate the cache after updating index.html."
  value       = aws_cloudfront_distribution.app.id
}
