variable "service_name" {
  description = "Service name prefix for all resource names."
  type        = string
}

variable "stage" {
  description = "Deployment stage name."
  type        = string
}

variable "api_version" {
  description = "API version string appended to the printed invoke URL. Cosmetic -- the {proxy+} resource routes every path regardless of this value, matching template.yaml's own ApiGatewayEndpoint output exactly."
  type        = string
  default     = "v1"
}

variable "backend_url" {
  description = "HTTP_PROXY integration target every request is forwarded to (e.g. http://api:8000, or a real ALB DNS name in the cloud)."
  type        = string
}

variable "rate_limit_per_second" {
  type    = number
  default = 50
}

variable "rate_limit_burst" {
  type    = number
  default = 100
}

variable "rate_limit_quota_per_day" {
  type    = number
  default = 10000
}

variable "local_emulator" {
  description = "True when deploying against a local AWS emulator (Floci). Gates whether local_invoke_url is computed."
  type        = bool
  default     = false
}

variable "local_emulator_endpoint_url" {
  description = "Base URL of the local emulator, used to construct local_invoke_url. Only read when local_emulator = true."
  type        = string
  default     = "http://localhost:4566"
}

variable "create_api_key" {
  description = <<-EOT
    Whether to create the API key, usage plan, and usage plan key
    (and require the key on both methods). Default true -- real AWS
    deploys always want this. False exists specifically because
    aws_api_gateway_api_key crashes the Terraform AWS provider
    (confirmed on both the ~> 5.0 and ~> 6.0 constraint lines) when
    read back against Floci: Floci's CreateApiKey/GetApiKey responses
    omit createdDate/lastUpdatedDate entirely, fields real AWS always
    populates, and the provider's read path dereferences one of them
    without a nil check. This can never trigger against real AWS.
    dev.floci.tfvars sets this false until Floci fixes the gap or the
    provider adds a nil check -- not a permanent design choice, a
    workaround for a specific, cited external bug.
  EOT
  type        = bool
  default     = true
}

variable "enable_access_logging" {
  description = <<-EOT
    Whether to include the access_log_settings block at all. Kept as
    a separate, plain boolean rather than inferring it from whether
    access_log_destination_arn is null -- found the hard way during
    the full-stack integration test: access_log_destination_arn comes
    from another module's output (observability's log_group_id) and
    is not known until apply time on a first-ever apply, and a
    dynamic block's for_each cardinality must be knowable at plan
    time. Gating for_each on this plain, always-known-at-plan-time
    boolean instead fixes that; the still-possibly-unknown-till-apply
    ARN itself is only used inside the block's contents once it's
    confirmed to exist, which Terraform has no problem with.
  EOT
  type        = bool
  default     = false
}

variable "access_log_destination_arn" {
  description = <<-EOT
    CloudWatch Logs group ARN for API Gateway access logs. Only read
    when enable_access_logging = true.
  EOT
  type        = string
  default     = null
}
