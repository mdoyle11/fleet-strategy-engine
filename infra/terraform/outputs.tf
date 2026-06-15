output "artifact_bucket_name" {
  description = "S3 bucket for raw uploads and processed recommendation artifacts."
  value       = aws_s3_bucket.artifacts.bucket
}

output "dashboard_artifact_base_uri" {
  description = "Value to use for FLEET_ARTIFACT_BASE_URI in the dashboard runtime."
  value       = "s3://${aws_s3_bucket.artifacts.bucket}/processed/runs"
}

output "dashboard_raw_upload_base_uri" {
  description = "Value to use for FLEET_RAW_UPLOAD_BASE_URI when Lambda execution is enabled."
  value       = "s3://${aws_s3_bucket.artifacts.bucket}/raw/uploads"
}

output "pipeline_lambda_repository_url" {
  description = "ECR repository URL for the pipeline Lambda container image."
  value       = aws_ecr_repository.pipeline_lambda.repository_url
}

output "pipeline_lambda_function_name" {
  description = "Pipeline Lambda function name, once lambda_image_uri is provided."
  value       = var.lambda_image_uri == "" ? "" : aws_lambda_function.pipeline[0].function_name
}

output "dashboard_repository_url" {
  description = "ECR repository URL for the Streamlit dashboard container image."
  value       = aws_ecr_repository.dashboard.repository_url
}

output "dashboard_url" {
  description = "Public dashboard URL, once dashboard_image_uri is provided."
  value = var.dashboard_image_uri == "" ? "" : try(
    one([
      for path in aws_ecs_express_gateway_service.dashboard[0].ingress_paths :
      path.endpoint
      if path.access_type == "PUBLIC"
    ]),
    aws_ecs_express_gateway_service.dashboard[0].ingress_paths[0].endpoint,
    "",
  )
}

output "google_api_key_parameter_name" {
  description = "Suggested SSM parameter name for the dashboard GOOGLE_API_KEY."
  value       = "/${var.project_name}/${var.environment}/google-api-key"
}
