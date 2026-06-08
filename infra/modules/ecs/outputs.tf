output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "implementer_task_definition_arn" {
  value = aws_ecs_task_definition.implementer.arn
}

output "crawler_task_definition_arn" {
  value = aws_ecs_task_definition.crawler.arn
}

output "ui_planner_task_definition_arn" {
  value = aws_ecs_task_definition.ui_planner.arn
}

output "security_group_id" {
  value = aws_security_group.fargate_tasks.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.agents.repository_url
}
