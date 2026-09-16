# secrets module — GCP (not implemented)

No `.tf` files here yet. This is the interface contract a real
implementation must satisfy, copied verbatim from `../aws/variables.tf`
and `../aws/outputs.tf` so the root module never has to change its
calling convention regardless of which provider backs it.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `secret_name` | `string` | — | Name for the secret |
| `username` | `string` | — | Seed username stored in the secret's payload |
| `generate_password` | `bool` | `true` | Must be `true` today, same as the AWS implementation — no caller-supplied-password input exists yet |
| `password_length` | `number` | `16` | Length of the generated password |
| `parameters` | `map(string)` | `{}` | Arbitrary small named string values, independent of the secret |
| `secret_arn_parameter_name` | `string` | `null` | If set, also publish this secret's own reference under this name |
| `force_delete_without_recovery` | `bool` | `false` | Skip any provider-side recovery/soft-delete window on destroy. GCP Secret Manager has no recovery-window concept at all (deletes are immediate) — this variable should still exist on this implementation for interface parity, but may be a no-op there. Confirm rather than assume when implementing. |

## Outputs

| Name | Description |
|---|---|
| `secret_reference` | Provider-shaped reference to the created secret |
| `parameter_references` | Map of parameter name -> reference, same keying rules as the AWS module |

## Candidate GCP resources

- `google_secret_manager_secret` + `google_secret_manager_secret_version` for the main secret (fed by the *same* `random_password` resource the AWS module uses — that resource is provider-agnostic, not an AWS call)
- **No separate parameter-store primitive exists on GCP** (Runtime Config is deprecated) — per the Part 2 investigation, `parameters` and `secret_arn_parameter_name` should both become additional `google_secret_manager_secret`/`google_secret_manager_secret_version` pairs here, not a different resource type. This is a real asymmetry with AWS (where SSM Parameter and Secrets Manager are two different services) worth keeping in mind when implementing this, not papering over.

## Status

Not implemented. Do not add a `provider "google" {}` block to the root
module's `providers.tf` until this module has real resources — see
`deploy/terraform/main.tf`'s `provider_name` variable validation.
