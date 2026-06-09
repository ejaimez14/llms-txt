output "role_arn" {
  description = "ARN of the IAM role — passed to Lambda and ECS modules."
  value       = aws_iam_role.app.arn
}
