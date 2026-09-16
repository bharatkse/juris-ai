# api-gateway module — Azure (not implemented)

No `.tf` files here yet. Same interface contract as `../gcp/README.md`
and `../aws/variables.tf`/`../aws/outputs.tf`.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `service_name` | `string` | — | Service name prefix |
| `stage` | `string` | — | Deployment stage name |
| `api_version` | `string` | `"v1"` | Cosmetic version string in the printed URL |
| `backend_url` | `string` | — | Proxy target every request forwards to |
| `rate_limit_per_second` | `number` | `50` | |
| `rate_limit_burst` | `number` | `100` | |
| `rate_limit_quota_per_day` | `number` | `10000` | |
| `local_emulator` | `bool` | `false` | Gates whether `local_invoke_url` is computed |
| `local_emulator_endpoint_url` | `string` | `"http://localhost:4566"` | Base URL for the local-emulator invoke URL |
| `access_log_destination_arn` | `string` | `null` | Log sink reference; null skips access logging |

## Outputs

| Name | Description |
|---|---|
| `endpoint_url` | Real invoke URL |
| `api_key_id` | Key identifier (not the value) |
| `local_invoke_url` | Local-emulator invoke URL, null unless `local_emulator = true` |

## Candidate Azure resources

- `azurerm_container_app` (or App Service) for the backend container
- `azurerm_api_management` + `azurerm_api_management_api` + `azurerm_api_management_backend` for the routing/proxy layer — APIM is a considerably heavier resource than AWS's API Gateway REST API (it's provisioned as a standing service with its own SKU/capacity, not a lightweight per-API resource), a real cost/operational difference worth surfacing before treating this as a drop-in equivalent
- `azurerm_api_management_subscription` for the API-key equivalent
- Rate limiting/quota on APIM is policy-XML-configured (`azurerm_api_management_api_policy` with an inline `<rate-limit>`/`<quota>` policy document), not a typed resource block the way AWS's `usage_plan` is — another genuine mechanism difference, not a naming exercise

## Status

Not implemented. Do not add a `provider "azurerm" {}` block to the root module's `providers.tf` until this module has real resources.
