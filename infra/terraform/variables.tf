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

variable "dashboard_image_uri" {
  description = "Container image URI for the Streamlit dashboard. Leave empty until the image is built and pushed."
  type        = string
  default     = ""
}

variable "dashboard_cpu" {
  description = "Fargate CPU units for the dashboard task."
  type        = number
  default     = 512
}

variable "dashboard_memory" {
  description = "Fargate memory in MiB for the dashboard task."
  type        = number
  default     = 1024
}

variable "dashboard_min_capacity" {
  description = "Minimum number of dashboard tasks for service autoscaling."
  type        = number
  default     = 1
}

variable "dashboard_max_capacity" {
  description = "Maximum number of dashboard tasks for service autoscaling."
  type        = number
  default     = 2
}

variable "google_api_key_parameter_name" {
  description = "Optional SSM Parameter Store SecureString name for GOOGLE_API_KEY. Leave empty to deploy the dashboard without the assistant key."
  type        = string
  default     = ""

  validation {
    condition     = var.google_api_key_parameter_name == "" || startswith(var.google_api_key_parameter_name, "/")
    error_message = "google_api_key_parameter_name must be empty or start with '/'."
  }
}

variable "ecr_max_images" {
  description = "Maximum number of container images to retain in each ECR repository."
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
