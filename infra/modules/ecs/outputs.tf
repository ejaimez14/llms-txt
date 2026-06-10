output "cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.agent.arn
}

output "implement_task_definition_arn" {
  value = aws_ecs_task_definition.implement.arn
}

output "security_group_id" {
  value = aws_security_group.fargate_tasks.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.agents.repository_url
}
