output "queue_url" {
  description = "URL of the SQS re-crawl queue — passed to Lambda as RECRAWL_QUEUE_URL."
  value       = aws_sqs_queue.recrawl.url
}
