terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # No google/azurerm required_providers entry yet -- neither has a
  # single real resource anywhere in this configuration. Add one only
  # when a gcp/ or azure/ module directory stops being a README stub,
  # per modules/secrets/{gcp,azure}/README.md's Status section.
}

provider "aws" {
  region = var.aws_region

  # Local-emulator (Floci) overrides -- real AWS deploys leave
  # local_emulator = false (the default) and pick up real credentials
  # from the environment/CLI profile as normal. See dev.floci.tfvars.
  access_key                  = var.local_emulator ? "test" : null
  secret_key                  = var.local_emulator ? "test" : null
  skip_credentials_validation = var.local_emulator
  skip_metadata_api_check     = var.local_emulator
  skip_requesting_account_id  = var.local_emulator

  # s3_use_path_style avoids depending on virtual-hosted-style bucket
  # addressing (LocalStack's own docs default to a
  # s3.localhost.localstack.cloud subdomain trick for that, which
  # hasn't been verified to work against Floci) -- path style is the
  # safer default for a local emulator.
  s3_use_path_style = var.local_emulator

  endpoints {
    secretsmanager = var.local_emulator ? var.local_emulator_endpoint_url : null
    ssm            = var.local_emulator ? var.local_emulator_endpoint_url : null
    apigateway     = var.local_emulator ? var.local_emulator_endpoint_url : null
    s3             = var.local_emulator ? var.local_emulator_endpoint_url : null
    cloudwatch     = var.local_emulator ? var.local_emulator_endpoint_url : null
    cloudwatchlogs = var.local_emulator ? var.local_emulator_endpoint_url : null
  }
}
