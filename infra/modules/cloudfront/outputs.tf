output "cloudfront_url" {
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
  description = "Public CloudFront URL"
}

output "frontend_bucket_name" {
  value       = aws_s3_bucket.frontend.id
  description = "Name of the S3 bucket used to serve the frontend"
}

output "cloudfront_distribution_id" {
  value       = aws_cloudfront_distribution.app.id
  description = "CloudFront distribution ID — needed for cache invalidation"
}
