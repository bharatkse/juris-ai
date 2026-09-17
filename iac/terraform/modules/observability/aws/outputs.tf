output "log_group_id" {
  description = "CloudWatch Logs log group ARN."
  value       = aws_cloudwatch_log_group.this.arn
}

output "alarm_ids" {
  description = "Map of alarm key ('4xx', '5xx') -> alarm ARN."
  value = {
    "4xx" = aws_cloudwatch_metric_alarm.four_xx.arn
    "5xx" = aws_cloudwatch_metric_alarm.five_xx.arn
  }
}
