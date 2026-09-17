terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

data "aws_region" "current" {}

resource "aws_api_gateway_rest_api" "this" {
  name = "${var.service_name}-api-${var.stage}"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# {proxy+} resource -- all routes other than the bare root path.
resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  parent_id   = aws_api_gateway_rest_api.this.root_resource_id
  path_part   = "{proxy+}"
}

# ANY / -- root method
resource "aws_api_gateway_method" "root_any" {
  rest_api_id      = aws_api_gateway_rest_api.this.id
  resource_id      = aws_api_gateway_rest_api.this.root_resource_id
  http_method      = "ANY"
  authorization    = "NONE"
  api_key_required = var.create_api_key
}

resource "aws_api_gateway_integration" "root_any" {
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_rest_api.this.root_resource_id
  http_method             = aws_api_gateway_method.root_any.http_method
  type                    = "HTTP_PROXY"
  integration_http_method = "ANY"
  uri                     = "${var.backend_url}/"
  passthrough_behavior    = "WHEN_NO_MATCH"
  timeout_milliseconds    = 29000

  # Confirmed Floci gap (see variables.tf's create_api_key comment for
  # the sibling gap on the same resource type): Floci accepts
  # timeout_milliseconds on create but GetIntegration always reads it
  # back as 0, and UpdateIntegration rejects patching
  # /timeoutInMillis outright ("Unsupported path"). Neither
  # lifecycle.ignore_changes nor setting this to null against Floci
  # fixes it -- both were tried and both still fail, because the
  # refreshed value (0) fails the provider's own "must be at least
  # 50" validation regardless of what the config says, and omitting
  # the argument just makes the provider substitute its own 29000
  # default as the desired value, which is right back to the same
  # 0-vs-29000 permanent drift. A FRESH `terraform apply` against
  # Floci creates this correctly and the live functional test proves
  # it (see the parity report) -- what does NOT work is a *second*
  # plan/apply against an already-created Floci stack, which will
  # show unfixable drift here and fail if actually applied. Treat
  # Floci-targeted apply/destroy cycles as always-fresh, never
  # incremental, for this resource. Real AWS is unaffected (its
  # GetIntegration correctly returns whatever was set).
}

# ANY /{proxy+} -- every other route.
#
# Deliberately no request_parameters mapping for {proxy} here. This
# matches template.yaml's JurisAIProxyMethod exactly as written --
# that CFN resource has no RequestParameters block either, and was
# proven this session (real HTTP request through this exact resource
# shape, live functional test) to correctly substitute {proxy} and
# return a real response from Floci. Building to match that proven
# baseline first, on purpose, rather than adding the request_parameters
# mapping AWS's own docs usually call for -- if Terraform's raw
# resources behave differently from CFN's shorthand here, the parity
# live-functional test below is what actually catches it, not an
# assumption made while writing this file.
resource "aws_api_gateway_method" "proxy_any" {
  rest_api_id      = aws_api_gateway_rest_api.this.id
  resource_id      = aws_api_gateway_resource.proxy.id
  http_method      = "ANY"
  authorization    = "NONE"
  api_key_required = var.create_api_key
}

resource "aws_api_gateway_integration" "proxy_any" {
  rest_api_id             = aws_api_gateway_rest_api.this.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy_any.http_method
  type                    = "HTTP_PROXY"
  integration_http_method = "ANY"
  uri                     = "${var.backend_url}/{proxy}"
  passthrough_behavior    = "WHEN_NO_MATCH"
  timeout_milliseconds    = 29000

  # See root_any's identical comment above -- same confirmed Floci gap.
}

resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id

  # Standard Terraform pattern for forcing redeployment whenever the
  # methods/integrations change -- documented in the AWS provider's
  # own aws_api_gateway_deployment examples, not invented here.
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_method.root_any.id,
      aws_api_gateway_integration.root_any.id,
      aws_api_gateway_method.proxy_any.id,
      aws_api_gateway_integration.proxy_any.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "this" {
  rest_api_id   = aws_api_gateway_rest_api.this.id
  deployment_id = aws_api_gateway_deployment.this.id
  stage_name    = var.stage

  dynamic "access_log_settings" {
    for_each = var.enable_access_logging ? [1] : []
    content {
      destination_arn = var.access_log_destination_arn
      format          = jsonencode({ requestId = "$context.requestId" })
    }
  }
}

# Terraform splits CFN's inline Stage.MethodSettings into its own
# resource -- same category of structural difference as S3's
# versioning/CORS/encryption split in the storage module (not yet
# built), not a naming exercise.
#
# Note for the live test: logging_level = "INFO" (execution logging,
# distinct from the access_log_settings block above) requires a
# CloudWatch Logs role configured at the AWS-account level via a
# separate aws_api_gateway_account resource on real AWS -- a
# singleton this module deliberately doesn't create (it isn't owned
# by any one module cleanly, and creating it here could conflict with
# another stack). Whether Floci enforces this the way real AWS does
# is exactly what the live apply is about to tell us -- not assumed
# here either way.
resource "aws_api_gateway_method_settings" "this" {
  rest_api_id = aws_api_gateway_rest_api.this.id
  stage_name  = aws_api_gateway_stage.this.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled        = true
    logging_level          = "INFO"
    throttling_rate_limit  = var.rate_limit_per_second
    throttling_burst_limit = var.rate_limit_burst
  }
}

# count-gated by create_api_key -- see variables.tf for why this can
# be false at all (a cited, confirmed Floci/provider incompatibility,
# not a permanent design choice).
resource "aws_api_gateway_api_key" "this" {
  count = var.create_api_key ? 1 : 0

  name    = "${var.service_name}-api-key-${var.stage}"
  enabled = true
}

resource "aws_api_gateway_usage_plan" "this" {
  count = var.create_api_key ? 1 : 0

  name        = "${var.service_name}-usage-plan-${var.stage}"
  description = "Rate limiting and quota for ${var.service_name}"

  api_stages {
    api_id = aws_api_gateway_rest_api.this.id
    stage  = aws_api_gateway_stage.this.stage_name
  }

  throttle_settings {
    rate_limit  = var.rate_limit_per_second
    burst_limit = var.rate_limit_burst
  }

  quota_settings {
    limit  = var.rate_limit_quota_per_day
    period = "DAY"
  }
}

resource "aws_api_gateway_usage_plan_key" "this" {
  count = var.create_api_key ? 1 : 0

  key_id        = aws_api_gateway_api_key.this[0].id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.this[0].id
}
