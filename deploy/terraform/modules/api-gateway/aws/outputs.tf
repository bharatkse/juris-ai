output "endpoint_url" {
  description = "Real AWS invoke URL. Meaningless against Floci -- see local_invoke_url for that case."
  value       = "https://${aws_api_gateway_rest_api.this.id}.execute-api.${data.aws_region.current.region}.amazonaws.com/${var.stage}/${var.api_version}"
}

output "api_key_id" {
  description = "API key ID -- use `aws apigateway get-api-key --api-key <id> --include-value` to retrieve the actual key value, same as today's SAM output. Null when create_api_key = false."
  value       = try(aws_api_gateway_api_key.this[0].id, null)
}

output "local_invoke_url" {
  description = "Local-emulator invoke URL (mirrors template.yaml's LocalStackApiEndpoint output). Null unless local_emulator = true."
  value       = var.local_emulator ? "${var.local_emulator_endpoint_url}/restapis/${aws_api_gateway_rest_api.this.id}/${var.stage}/_user_request_/" : null
}
