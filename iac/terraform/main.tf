# Root module. secrets, api-gateway, storage, and observability are
# all wired in now -- Phase 1's four modules are complete for AWS.
#
# Provider-selection pattern: Terraform's module `source` argument
# cannot contain variable interpolation (a long-standing, still-open
# upstream limitation), so provider selection can't be
# "source = ./modules/x/${var.provider_name}". Instead every provider's
# module block is declared with a static source path and gated with
# count, and callers read whichever one actually got created via
# try(). This is the standard pattern for this exact need, not a
# workaround specific to this project.
module "secrets_aws" {
  source = "./modules/secrets/aws"
  count  = var.provider_name == "aws" ? 1 : 0

  secret_name                   = "${var.service_name}-db-secret-${var.stage}"
  username                      = var.db_username
  generate_password             = true
  password_length               = 16
  force_delete_without_recovery = var.force_delete_without_recovery

  parameters = {}

  # Mirrors template.yaml's DBSecretArnParameter -- see
  # modules/secrets/aws/variables.tf for why this isn't threaded
  # through the generic `parameters` map instead.
  secret_arn_parameter_name = "/${var.service_name}/${var.stage}/db-secret-arn"
}

# Added only once modules/secrets/gcp/ stops being a README stub:
# module "secrets_gcp" {
#   source = "./modules/secrets/gcp"
#   count  = var.provider_name == "gcp" ? 1 : 0
#   ...
# }

module "api_gateway_aws" {
  source = "./modules/api-gateway/aws"
  count  = var.provider_name == "aws" ? 1 : 0

  service_name             = var.service_name
  stage                    = var.stage
  api_version              = var.api_version
  backend_url              = var.backend_url
  rate_limit_per_second    = var.rate_limit_per_second
  rate_limit_burst         = var.rate_limit_burst
  rate_limit_quota_per_day = var.rate_limit_quota_per_day

  local_emulator              = var.local_emulator
  local_emulator_endpoint_url = var.local_emulator_endpoint_url

  # enable_access_logging = var.provider_name == "aws" -- a plain,
  # always-known-at-plan-time boolean, not derived from whether the
  # ARN below happens to be null. Found the hard way during the
  # full-stack integration test: gating on the ARN's nullness broke
  # on a first-ever apply, since that ARN comes from
  # observability_aws's output and isn't known until apply time, and
  # dynamic-block for_each cardinality must be knowable at plan time.
  # See modules/api-gateway/aws/variables.tf's enable_access_logging.
  enable_access_logging      = var.provider_name == "aws"
  access_log_destination_arn = try(module.observability_aws[0].log_group_id, null)

  create_api_key = var.create_api_key
}

# Added only once modules/api-gateway/gcp/ stops being a README stub:
# module "api_gateway_gcp" {
#   source = "./modules/api-gateway/gcp"
#   count  = var.provider_name == "gcp" ? 1 : 0
#   ...
# }

module "storage_aws" {
  source = "./modules/storage/aws"
  count  = var.provider_name == "aws" ? 1 : 0

  bucket_name          = "${var.service_name}-documents-${var.stage}"
  versioning_enabled   = var.document_bucket_versioning_enabled
  cors_allowed_origins = var.cors_allowed_origins
}

# Added only once modules/storage/gcp/ stops being a README stub:
# module "storage_gcp" {
#   source = "./modules/storage/gcp"
#   count  = var.provider_name == "gcp" ? 1 : 0
#   ...
# }

module "observability_aws" {
  source = "./modules/observability/aws"
  count  = var.provider_name == "aws" ? 1 : 0

  log_group_name      = "/aws/apigateway/${var.service_name}-${var.stage}"
  retention_in_days   = var.log_retention_in_days
  alarm_4xx_threshold = var.alarm_4xx_threshold
  alarm_5xx_threshold = var.alarm_5xx_threshold

  # The REST API's actual Name, computed the same way
  # module.api_gateway_aws derives it internally -- not read back as
  # a module output, since root already has everything needed to
  # compute it directly and doing so avoids a dependency edge running
  # the "wrong" direction (api_gateway_aws depends on
  # observability_aws's log_group_id above; observability_aws must
  # not turn around and depend on api_gateway_aws's outputs too).
  api_gateway_name = "${var.service_name}-api-${var.stage}"
}

# Added only once modules/observability/gcp/ stops being a README stub:
# module "observability_gcp" {
#   source = "./modules/observability/gcp"
#   count  = var.provider_name == "gcp" ? 1 : 0
#   ...
# }
