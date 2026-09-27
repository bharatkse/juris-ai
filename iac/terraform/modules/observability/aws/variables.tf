variable "log_group_name" {
  description = "CloudWatch Logs log group name."
  type        = string
}

variable "retention_in_days" {
  description = "Log retention period, in days. Mirrors template.yaml's hardcoded RetentionInDays: 30."
  type        = number
  default     = 30
}

variable "alarm_4xx_threshold" {
  description = "4XX error count threshold -- mirrors template.yaml's ApiGateway4XXAlarm Threshold: 50."
  type        = number
  default     = 50
}

variable "alarm_5xx_threshold" {
  description = "5XX error count threshold -- mirrors template.yaml's ApiGateway5XXAlarm Threshold: 10."
  type        = number
  default     = 10
}

variable "api_gateway_name" {
  description = <<-EOT
    The REST API's Name (not its ID) -- used as both alarms' ApiName
    dimension. Note: template.yaml's own alarms use `!Ref
    JurisAIRestApi` for this, which CloudFormation resolves to the
    REST API's ID, not its Name -- AWS's own CloudWatch documentation
    states the ApiName dimension expects the API's Name. That looks
    like a pre-existing bug in template.yaml, unrelated to Floci (it
    would misbehave identically on real AWS: the alarms would never
    match real published metric data, which is dimensioned by name).
    Not fixed in template.yaml as part of this module -- flagging it,
    not silently carrying it forward. This module takes the actual
    name deliberately, matching what this variable is named.
  EOT
  type        = string
}
