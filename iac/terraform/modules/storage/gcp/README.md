# storage module — GCP (not implemented)

No `.tf` files here yet. Interface contract, copied verbatim from
`../aws/variables.tf` and `../aws/outputs.tf`.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `bucket_name` | `string` | — | Bucket name |
| `versioning_enabled` | `bool` | `true` | Whether object versioning is enabled |
| `cors_allowed_origins` | `list(string)` | `["*"]` | Allowed CORS origins. The rest of the CORS rule shape (methods, headers, max age) is hardcoded to match the AWS module's values on that implementation — decide on implementing whether to keep that hardcoding here too or expose it, but don't silently pick different hardcoded values than the AWS side without a reason. |

## Outputs

| Name | Description |
|---|---|
| `bucket_name` | The created bucket's name |
| `bucket_reference` | Provider-shaped identifier (self-link on GCP, not an ARN) |

## Candidate GCP resources

- `google_storage_bucket` — GCS supports versioning, CORS, and default encryption as *inline* properties on this single resource (`versioning { enabled = ... }`, `cors { ... }`, `encryption { default_kms_key_name = ... }` blocks), unlike AWS's split into five separate resources. Don't mechanically recreate five GCP resources to mirror the AWS module's file structure — one `google_storage_bucket` resource with inline blocks is the idiomatic, correct shape here. The "same category of structural difference" comment in the AWS module's `main.tf` is about CFN-vs-Terraform on the *same* cloud, not a rule that every cloud needs the same number of resources.
- **Public access block has no default-encryption-key equivalent constraint** worth noting: GCS buckets are private by default and "public access prevention" is its own top-level property (`public_access_prevention = "enforced"`), not four separate booleans the way AWS splits ACL/policy/ignore/restrict. Map `block_public_acls`/`block_public_policy`/`ignore_public_acls`/`restrict_public_buckets` (all hardcoded `true` on the AWS side) to this one GCP setting rather than inventing four GCP-side booleans that don't correspond to anything real.

## Status

Not implemented. Do not add a `provider "google" {}` block to the root module's `providers.tf` until this module has real resources.
