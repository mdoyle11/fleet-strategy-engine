variable "aws_region" {
  description = "AWS region for fleet strategy resources."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name prefix for AWS resources."
  type        = string
  default     = "fleet-strategy-engine"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "lambda_image_uri" {
  description = "Container image URI for the pipeline Lambda. Leave empty until the image is built and pushed."
  type        = string
  default     = ""
}

variable "ecr_max_images" {
  description = "Maximum number of Lambda container images to retain in ECR."
  type        = number
  default     = 2
}

variable "raw_upload_expiration_days" {
  description = "Number of days to retain raw CSV uploads in S3."
  type        = number
  default     = 7
}

variable "processed_run_expiration_days" {
  description = "Number of days to retain processed pipeline run artifacts in S3."
  type        = number
  default     = 30
}

variable "noncurrent_version_expiration_days" {
  description = "Number of days to retain noncurrent S3 object versions."
  type        = number
  default     = 7
}
