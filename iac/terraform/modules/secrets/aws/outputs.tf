output "secret_reference" {
  description = "ARN of the created Secrets Manager secret."
  value       = aws_secretsmanager_secret.this.arn
}

output "parameter_references" {
  description = <<-EOT
    Map of parameter name -> SSM parameter ARN. Includes every entry
    from the `parameters` input plus, when set, the
    secret_arn_parameter_name entry -- keyed the same way in both
    cases so callers don't need to know which path a given parameter
    came from.
  EOT
  value = merge(
    { for name, param in aws_ssm_parameter.this : name => param.arn },
    var.secret_arn_parameter_name != null ? {
      (var.secret_arn_parameter_name) = aws_ssm_parameter.secret_arn[0].arn
    } : {}
  )
}
