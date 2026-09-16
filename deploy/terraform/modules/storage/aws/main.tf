terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

resource "aws_s3_bucket" "this" {
  bucket = var.bucket_name
}

# Terraform splits CFN's inline VersioningConfiguration into its own
# resource -- same category of structural difference already hit on
# API Gateway's Stage.MethodSettings, not a naming exercise.
resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id

  versioning_configuration {
    status = var.versioning_enabled ? "Enabled" : "Suspended"
  }
}

# Matches template.yaml's BucketEncryption exactly -- AES256 is the
# only algorithm the CFN template specifies. No input variable for
# algorithm choice: the interface contract didn't ask for one.
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Matches template.yaml's CorsConfiguration exactly. Allowed
# headers/methods, max age, and exposed headers are hardcoded to the
# same values as the CFN template -- the interface contract only
# exposes cors_allowed_origins, not the rest of the rule shape.
resource "aws_s3_bucket_cors_configuration" "this" {
  bucket = aws_s3_bucket.this.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "DELETE", "HEAD"]
    allowed_origins = var.cors_allowed_origins
    expose_headers  = ["ETag", "x-amz-request-id"]
    max_age_seconds = 3600
  }
}

# Matches template.yaml's PublicAccessBlockConfiguration exactly --
# all four flags true, the most restrictive setting, same as the CFN
# baseline. No input variable: the interface contract didn't ask for
# one and there's no case in this project where a less restrictive
# value would be wanted.
resource "aws_s3_bucket_public_access_block" "this" {
  bucket = aws_s3_bucket.this.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
