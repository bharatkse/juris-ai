output "secret_reference" {
  description = "ARN of the DB secret, from whichever provider module is active."
  value       = try(module.secrets_aws[0].secret_reference, null)
}

output "parameter_references" {
  description = "Map of parameter name -> reference, from whichever provider module is active."
  value       = try(module.secrets_aws[0].parameter_references, null)
}

output "api_endpoint_url" {
  description = "Real invoke URL, from whichever provider module is active."
  value       = try(module.api_gateway_aws[0].endpoint_url, null)
}

output "api_key_id" {
  description = "API key identifier, from whichever provider module is active."
  value       = try(module.api_gateway_aws[0].api_key_id, null)
}

output "api_local_invoke_url" {
  description = "Local-emulator invoke URL, from whichever provider module is active. Null unless local_emulator = true."
  value       = try(module.api_gateway_aws[0].local_invoke_url, null)
}

output "document_bucket_name" {
  description = "Document bucket name, from whichever provider module is active."
  value       = try(module.storage_aws[0].bucket_name, null)
}

output "document_bucket_reference" {
  description = "Document bucket reference (ARN on AWS), from whichever provider module is active."
  value       = try(module.storage_aws[0].bucket_reference, null)
}

output "log_group_id" {
  description = "CloudWatch Logs log group ARN, from whichever provider module is active."
  value       = try(module.observability_aws[0].log_group_id, null)
}

output "alarm_ids" {
  description = "Map of alarm key -> alarm ARN, from whichever provider module is active."
  value       = try(module.observability_aws[0].alarm_ids, null)
}
