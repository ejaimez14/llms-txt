variable "lambda_invoke_arn" {
  description = "Invoke ARN of the Lambda function that handles all API routes."
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the Lambda function, used to grant invocation permission."
  type        = string
}
