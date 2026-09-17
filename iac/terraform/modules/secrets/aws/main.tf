terraform {
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
}

# Generated client-side by Terraform, not resolved via any AWS API --
# this is the real, if slightly less declarative, equivalent of CFN's
# GenerateSecretString. override_special mirrors template.yaml's
# ExcludeCharacters: '"@/\' on the one character actually present in
# Terraform's default special set ("@"); '"', '/', '\' were never in
# that default set to begin with, so nothing else needs excluding.
resource "random_password" "db" {
  length           = var.password_length
  special          = true
  override_special = "!#$%^&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "this" {
  name        = var.secret_name
  description = "Managed by Terraform (secrets/aws module) -- ${var.secret_name}"

  # The resource has no boolean force-delete argument -- only
  # recovery_window_in_days (confirmed against the actual installed
  # provider schema after a first, wrong attempt at this failed
  # `terraform validate`). 0 maps to the real API's
  # ForceDeleteWithoutRecovery=true; null omits the argument entirely,
  # which is what produced AWS's real 30-day-default soft-delete
  # behavior proven empirically in the secrets module's parity test.
  recovery_window_in_days = var.force_delete_without_recovery ? 0 : null
}

# Same JSON shape as template.yaml's SecretStringTemplate +
# GenerateStringKey combination: {"username": ..., "password": ...}.
resource "aws_secretsmanager_secret_version" "this" {
  secret_id = aws_secretsmanager_secret.this.id

  secret_string = jsonencode({
    username = var.username
    password = random_password.db.result
  })
}

resource "aws_ssm_parameter" "this" {
  for_each = var.parameters

  name  = each.key
  type  = "String"
  value = each.value
}

resource "aws_ssm_parameter" "secret_arn" {
  count = var.secret_arn_parameter_name != null ? 1 : 0

  name  = var.secret_arn_parameter_name
  type  = "String"
  value = aws_secretsmanager_secret.this.arn
}
