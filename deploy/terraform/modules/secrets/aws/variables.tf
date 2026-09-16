variable "secret_name" {
  description = "Name for the Secrets Manager secret."
  type        = string
}

variable "username" {
  description = "Seed username value stored in the secret's JSON payload."
  type        = string
}

variable "generate_password" {
  description = <<-EOT
    Whether to auto-generate the password via Terraform's random_password
    resource (client-side, not an AWS call -- Secrets Manager has no
    built-in "generate for me" the way CFN's GenerateSecretString does).
    Must be true today: there is no module input for a caller-supplied
    password yet, so generate_password = false has nothing to fall back
    to. Kept as an explicit variable (with this validation) rather than
    hardcoded true, so adding a real "password" input later is a
    non-breaking change to this module's contract instead of a new one.
  EOT
  type        = bool
  default     = true

  validation {
    condition     = var.generate_password == true
    error_message = "generate_password = false is not implemented yet -- this module has no caller-supplied-password input to fall back to."
  }
}

variable "password_length" {
  description = "Length of the generated password, when generate_password is true."
  type        = number
  default     = 16
}

variable "parameters" {
  description = <<-EOT
    Arbitrary small named string values to store as individual SSM
    String parameters, independent of the secret created by this
    module. Map key = parameter name (path), map value = parameter
    value. Empty by default. This is NOT how the secret's own ARN gets
    published as a parameter -- see secret_arn_parameter_name for that
    (a parameter value derived from this module's own secret can't be
    threaded through this generic map without a circular reference).
  EOT
  type        = map(string)
  default     = {}
}

variable "force_delete_without_recovery" {
  description = <<-EOT
    Maps to aws_secretsmanager_secret's recovery_window_in_days (true
    -> 0, which the provider translates to the real API's
    ForceDeleteWithoutRecovery=true; false -> null, omitting the
    argument entirely). Real AWS (and Floci, proven to replicate this
    faithfully) defaults a plain DeleteSecret to a 30-day recovery
    window -- describe-secret keeps returning metadata and
    get-secret-value fails with "marked for deletion" until the
    window elapses. Default false so production/snd behavior is the
    real, unmodified AWS default; dev/test tfvars set this true for
    fast, repeatable teardown cycles instead of waiting on (or
    fighting) the recovery window.
  EOT
  type        = bool
  default     = false
}

variable "secret_arn_parameter_name" {
  description = <<-EOT
    If set, also create an SSM String parameter at this path holding
    this secret's own ARN (mirrors template.yaml's DBSecretArnParameter
    output). Null skips it. Kept separate from the generic `parameters`
    map on purpose: a resource cannot reference its own sibling
    resource's attribute through a generic input map without Terraform
    treating it as a circular reference, since both would be created in
    the same module call. This gives the self-referential case its own
    explicit, non-circular path instead.
  EOT
  type        = string
  default     = null
}
