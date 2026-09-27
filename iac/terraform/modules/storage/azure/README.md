# storage module — Azure (not implemented)

No `.tf` files here yet. Same interface contract as `../gcp/README.md`
and `../aws/variables.tf`/`../aws/outputs.tf`.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `bucket_name` | `string` | — | Container/storage-account name — see the note below on the naming mismatch |
| `versioning_enabled` | `bool` | `true` | Whether blob versioning is enabled |
| `cors_allowed_origins` | `list(string)` | `["*"]` | Allowed CORS origins |

## Outputs

| Name | Description |
|---|---|
| `bucket_name` | The created container's name |
| `bucket_reference` | Provider-shaped identifier (resource ID on Azure, not an ARN) |

## Candidate Azure resources

- `azurerm_storage_account` (the actual "bucket"-equivalent object-storage namespace) + `azurerm_storage_container` (the specific container inside it) — Azure's storage model is two-tiered where AWS's/GCP's is one-tiered (a bucket is both the namespace and the container). `bucket_name` as a single string input doesn't map cleanly onto "account name" + "container name" as two separate required, differently-constrained identifiers (storage account names have their own, stricter naming rules than container names) — resolve this deliberately when implementing, don't just feed `bucket_name` into both.
- `azurerm_storage_account`'s `blob_properties.versioning_enabled` for versioning, `azurerm_storage_account`'s `blob_properties.cors_rule` for CORS
- Encryption is on-by-default at the storage-account level on Azure (customer-managed or Microsoft-managed keys), not an opt-in per-bucket property the way AWS's `aws_s3_bucket_server_side_encryption_configuration` is — there may be nothing to explicitly configure here to match the AWS module's AES256 setting, or it may need an explicit `infrastructure_encryption_enabled` — confirm rather than assume.
- Public access control: `azurerm_storage_account.public_network_access_enabled` / container-level `container_access_type = "private"` are the closest equivalents to AWS's four public-access-block booleans, but again not a 1:1 field mapping.

## Status

Not implemented. Do not add a `provider "azurerm" {}` block to the root module's `providers.tf` until this module has real resources.
