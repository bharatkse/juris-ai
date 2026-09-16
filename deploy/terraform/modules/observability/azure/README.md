# observability module — Azure (not implemented)

No `.tf` files here yet. Same interface contract as `../gcp/README.md`
and `../aws/variables.tf`/`../aws/outputs.tf`.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `log_group_name` | `string` | — | Log Analytics workspace / log category name |
| `retention_in_days` | `number` | `30` | Log retention period |
| `alarm_4xx_threshold` | `number` | `50` | 4XX error count threshold |
| `alarm_5xx_threshold` | `number` | `10` | 5XX error count threshold |
| `api_gateway_name` | `string` | — | The gateway's actual Name, used as the alert's target dimension |

## Outputs

| Name | Description |
|---|---|
| `log_group_id` | Provider-shaped log resource identifier |
| `alarm_ids` | Map of alarm key (`"4xx"`, `"5xx"`) -> alert rule identifier |

## Candidate Azure resources

- `azurerm_log_analytics_workspace` (retention lives here, via `retention_in_days` on the workspace itself — closer to AWS's per-log-group retention than GCP's bucket-level setting) for the log group equivalent
- `azurerm_monitor_metric_alert` for each alarm, with a `criteria` block referencing the APIM resource's metric (e.g. `Requests` filtered by response code range) — again condition/expression-based rather than the flat `metric_name`/`threshold` argument set AWS uses, same category of translation work noted in the GCP stub
- Azure Monitor's metric alert `scopes` argument needs the *resource ID* of the thing being monitored (the APIM instance from the `api-gateway` module, not just its name) — `api_gateway_name` alone may not be sufficient input here; likely needs a resource ID passed through instead or in addition. Confirm rather than assume when implementing.

## Status

Not implemented. Do not add a `provider "azurerm" {}` block to the root module's `providers.tf` until this module has real resources.
