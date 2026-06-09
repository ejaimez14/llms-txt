variable "queue_name" {
  description = "Name of the SQS re-crawl queue."
  type        = string
  default     = "llms-txt-recrawl"
}

variable "dlq_name" {
  description = "Name of the SQS dead-letter queue for failed re-crawl messages."
  type        = string
  default     = "llms-txt-recrawl-dlq"
}

variable "lambda_function_arn" {
  description = "ARN of the Lambda function that handles SQS re-crawl messages and EventBridge schedule events."
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the Lambda function, used to grant EventBridge invocation permission."
  type        = string
}
