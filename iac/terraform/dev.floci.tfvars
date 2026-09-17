# Local dev, against Floci -- matches the confirmed-working
# provider "aws" { endpoints {} } syntax (HashiCorp's own
# custom-service-endpoints guide + LocalStack's official Terraform
# docs), verified before this module was written.
#
# stage is deliberately "dev-tf", not "dev": today's real SAM deploy
# already owns juris-ai-db-secret-dev / /juris-ai/dev/db-secret-arn
# against this same Floci instance. Side-by-side parity testing needs
# genuinely distinct resource names, not a second deploy of the same
# names.
provider_name               = "aws"
local_emulator              = true
local_emulator_endpoint_url = "http://localhost:4566"
aws_region                  = "us-east-1"
service_name                = "juris-ai"
stage                       = "dev-tf"
db_username                 = "admin"

# Dev/test only -- skip Secrets Manager's 30-day recovery window so
# repeated apply/destroy cycles against Floci don't accumulate
# soft-deleted secrets or collide on names. Real AWS deploys must
# never set this true (see variables.tf).
force_delete_without_recovery = true

# api:8000 (the real Docker Compose service name on juris_ai_network),
# not host.docker.internal:8000 -- confirmed empirically this session
# that host.docker.internal does not resolve on native Linux Docker.
backend_url = "http://api:8000"

# Workaround for a confirmed Floci/provider crash: aws_api_gateway_api_key
# panics the AWS provider (nil dereference in resourceAPIKeyRead) because
# Floci's CreateApiKey/GetApiKey response omits createdDate/lastUpdatedDate,
# fields real AWS always populates. Reproduced identically on provider
# ~> 5.0 (v5.100.0) and ~> 6.0 (v6.64.0) -- not version-specific, and
# can never trigger against real AWS. Remove this override once Floci
# fixes the gap or the provider adds a nil check.
create_api_key = false
