variable "bucket_name" {
  description = "S3 bucket name."
  type        = string
}

variable "versioning_enabled" {
  description = "Whether object versioning is enabled on the bucket. Mirrors template.yaml's VersioningConfiguration.Status: Enabled."
  type        = bool
  default     = true
}

variable "cors_allowed_origins" {
  description = <<-EOT
    Allowed CORS origins. Mirrors template.yaml's AllowedOrigin
    parameter (a single string there, default "*"); this module takes
    a list since a CORS rule naturally supports multiple origins. The
    rest of the CORS rule shape (allowed headers/methods, max age,
    exposed headers) is hardcoded to match template.yaml exactly --
    the interface contract only exposes origins, not the rest of the
    rule.
  EOT
  type        = list(string)
  default     = ["*"]
}
