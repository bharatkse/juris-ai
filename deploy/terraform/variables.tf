variable "provider_name" {
  description = "Which cloud implementation to deploy. Only \"aws\" is implemented today."
  type        = string
  default     = "aws"

  validation {
    condition     = contains(["aws"], var.provider_name)
    error_message = "Only \"aws\" is implemented today. See modules/*/gcp/README.md and modules/*/azure/README.md for the not-yet-built contracts."
  }
}

variable "aws_region" {
  description = "AWS region for real deploys. Meaningless against Floci (local_emulator = true) but still required by the provider block."
  type        = string
  default     = "us-east-1"
}

variable "local_emulator" {
  description = "True when deploying against a local AWS emulator (Floci) instead of real AWS."
  type        = bool
  default     = false
}

variable "local_emulator_endpoint_url" {
  description = "Base URL of the local emulator (Floci), used for every overridden service endpoint. Only read when local_emulator = true."
  type        = string
  default     = "http://localhost:4566"
}

variable "service_name" {
  description = "Service name prefix for all resource names -- mirrors template.yaml's ServiceName parameter."
  type        = string
  default     = "juris-ai"
}

variable "stage" {
  description = "Deployment stage -- mirrors template.yaml's Stage parameter."
  type        = string
  default     = "local"
}

variable "db_username" {
  description = "Seed username stored in the DB secret's JSON payload -- mirrors template.yaml's DBSecret SecretStringTemplate."
  type        = string
  default     = "admin"
}

variable "force_delete_without_recovery" {
  description = <<-EOT
    Skip Secrets Manager's 30-day recovery window on delete. Default
    false (real AWS default, unmodified) for production/snd; dev
    tfvars set this true for fast, repeatable teardown cycles.
  EOT
  type        = bool
  default     = false
}

variable "api_version" {
  description = "API version string appended to the printed invoke URL -- mirrors template.yaml's ApiVersion parameter. Cosmetic: the {proxy+} resource routes every path regardless of this value."
  type        = string
  default     = "v1"
}

variable "backend_url" {
  description = <<-EOT
    HTTP_PROXY integration target the API Gateway forwards every
    request to. No default on purpose: template.yaml's own default
    (http://host.docker.internal:8000) only resolves on Docker
    Desktop, not native Linux Docker -- confirmed the hard way earlier
    this session. Each environment's tfvars must set this explicitly
    rather than inherit a default that's silently wrong half the time.
  EOT
  type        = string
}

variable "rate_limit_per_second" {
  description = "API Gateway throttle -- mirrors template.yaml's RateLimitPerSecond."
  type        = number
  default     = 50
}

variable "rate_limit_burst" {
  description = "API Gateway throttle burst -- mirrors template.yaml's RateLimitBurst."
  type        = number
  default     = 100
}

variable "rate_limit_quota_per_day" {
  description = "API Gateway usage plan daily quota -- mirrors template.yaml's RateLimitQuotaPerDay."
  type        = number
  default     = 10000
}

variable "create_api_key" {
  description = <<-EOT
    Default true (real AWS deploys always want the API key/usage
    plan). Dev tfvars set this false as a workaround for a confirmed
    Floci/provider crash on aws_api_gateway_api_key -- see
    modules/api-gateway/aws/variables.tf for the full explanation.
  EOT
  type        = bool
  default     = true
}

variable "document_bucket_versioning_enabled" {
  description = "Whether the document bucket has versioning enabled -- mirrors template.yaml's VersioningConfiguration.Status: Enabled."
  type        = bool
  default     = true
}

variable "cors_allowed_origins" {
  description = "Allowed CORS origins for the document bucket -- mirrors template.yaml's AllowedOrigin parameter (default \"*\")."
  type        = list(string)
  default     = ["*"]
}

variable "log_retention_in_days" {
  description = "API Gateway access-log retention -- mirrors template.yaml's ApiGatewayLogGroup RetentionInDays: 30."
  type        = number
  default     = 30
}

variable "alarm_4xx_threshold" {
  description = "4XX error count threshold -- mirrors template.yaml's ApiGateway4XXAlarm Threshold: 50."
  type        = number
  default     = 50
}

variable "alarm_5xx_threshold" {
  description = "5XX error count threshold -- mirrors template.yaml's ApiGateway5XXAlarm Threshold: 10."
  type        = number
  default     = 10
}
