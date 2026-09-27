output "bucket_name" {
  description = "The created bucket's name."
  value       = aws_s3_bucket.this.bucket
}

output "bucket_reference" {
  description = "Provider-shaped identifier for the bucket (ARN on AWS)."
  value       = aws_s3_bucket.this.arn
}
