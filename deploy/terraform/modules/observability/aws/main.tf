terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

resource "aws_cloudwatch_log_group" "this" {
  name              = var.log_group_name
  retention_in_days = var.retention_in_days
}

# Alarm names derived from api_gateway_name -- the interface contract
# has no separate service_name/stage input for this module, and
# api_gateway_name is the only identifying string available.
resource "aws_cloudwatch_metric_alarm" "four_xx" {
  alarm_name          = "${var.api_gateway_name}-4xx"
  alarm_description   = "High rate of client errors on API Gateway"
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.alarm_4xx_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = var.api_gateway_name
  }
}

resource "aws_cloudwatch_metric_alarm" "five_xx" {
  alarm_name          = "${var.api_gateway_name}-5xx"
  alarm_description   = "Server errors on API Gateway"
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = var.alarm_5xx_threshold
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = var.api_gateway_name
  }
}
