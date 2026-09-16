# observability module — GCP (not implemented)

No `.tf` files here yet. Interface contract, copied verbatim from
`../aws/variables.tf` and `../aws/outputs.tf`.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `log_group_name` | `string` | — | Log group/sink name |
| `retention_in_days` | `number` | `30` | Log retention period |
| `alarm_4xx_threshold` | `number` | `50` | 4XX error count threshold |
| `alarm_5xx_threshold` | `number` | `10` | 5XX error count threshold |
| `api_gateway_name` | `string` | — | The gateway's actual Name, used as the alarm dimension |

## Outputs

| Name | Description |
|---|---|
| `log_group_id` | Provider-shaped log sink identifier |
| `alarm_ids` | Map of alarm key (`"4xx"`, `"5xx"`) -> alarm identifier |

## Candidate GCP resources

- **Two separate services, not one**, per the Part 2 investigation: `google_logging_project_sink` (or a log-based metric) for the log group, and `google_monitoring_alert_policy` for each alarm. GCP splits "where logs go" from "what triggers an alert" more explicitly than AWS's CloudWatch does.
- Alerting on GCP is condition-expression-based (`google_monitoring_alert_policy.conditions.condition_threshold.filter`, a MQL/PromQL-like string), not a typed `metric_name`/`namespace`/`statistic`/`threshold` set of separate resource arguments the way `aws_cloudwatch_metric_alarm` is. Translating `alarm_4xx_threshold`/`alarm_5xx_threshold` into the right filter expression is real implementation work, not a field rename.
- Retention (`retention_in_days`) maps to a `google_logging_project_bucket_config` resource's `retention_days`, which is a *bucket*-level setting (potentially shared across multiple log sinks), not a property of the sink itself — confirm how this project wants to scope that before assuming one log group = one retention setting the way CloudWatch treats it.

## Status

Not implemented. Do not add a `provider "google" {}` block to the root module's `providers.tf` until this module has real resources.
