output "instance_id" {
  value = aws_instance.bot.id
}

output "public_ip" {
  value = aws_instance.bot.public_ip
}

output "security_group_id" {
  value = aws_security_group.bot.id
}

output "iam_role_arn" {
  value = aws_iam_role.bot_instance_role.arn
}

output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}
