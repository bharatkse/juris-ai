# secrets module — Azure (not implemented)

No `.tf` files here yet. Same interface contract as `../gcp/README.md`
and `../aws/variables.tf`/`../aws/outputs.tf` — repeated here rather
than cross-referenced only, so this file is self-sufficient for
whoever implements it.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `secret_name` | `string` | — | Name for the secret |
| `username` | `string` | — | Seed username stored in the secret's payload |
| `generate_password` | `bool` | `true` | Must be `true` today, same as the AWS implementation |
| `password_length` | `number` | `16` | Length of the generated password |
| `parameters` | `map(string)` | `{}` | Arbitrary small named string values, independent of the secret |
| `secret_arn_parameter_name` | `string` | `null` | If set, also publish this secret's own reference under this name |
| `force_delete_without_recovery` | `bool` | `false` | Skip any provider-side recovery/soft-delete window on destroy. Azure Key Vault has "soft-delete" enabled by default at the vault level (not per-secret, and often not disableable on the vault once purge protection is on) — confirm the actual vault's configuration before assuming this variable can be honored the same way the AWS implementation honors it. |

## Outputs

| Name | Description |
|---|---|
| `secret_reference` | Provider-shaped reference to the created secret |
| `parameter_references` | Map of parameter name -> reference, same keying rules as the AWS module |

## Candidate Azure resources

- `azurerm_key_vault_secret` for the main secret (fed by the same
  provider-agnostic `random_password` resource) — note this requires
  an `azurerm_key_vault` to already exist/be provisioned, which has no
  AWS-side equivalent resource in this module; that's a real structural
  difference to resolve during implementation, not a naming exercise.
- Azure Key Vault has no separate "parameter store" service either —
  `parameters` and `secret_arn_parameter_name` would both become
  additional `azurerm_key_vault_secret` entries, same asymmetry noted
  in the GCP stub.

## Status

Not implemented. Do not add a `provider "azurerm" {}` block to the root
module's `providers.tf` until this module has real resources.
