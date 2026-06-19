# Terraform

This is the AWS foundation for the fleet strategy deployment. It creates the S3 artifact bucket that holds raw uploads and processed pipeline outputs, ECR repositories for container images, the pipeline Lambda, and dashboard hosting resources.

The default retention settings are intentionally small for local MVP use:

- ECR keeps the latest 2 container images per repository.
- S3 raw uploads under `raw/uploads/` expire after 7 days.
- S3 processed runs under `processed/runs/` expire after 30 days.
- Noncurrent S3 object versions expire after 7 days.

S3 lifecycle rules do not enforce a hard bucket-size cap. They limit growth by deleting old objects and old versions after the configured retention windows.

```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

The dashboard can point at the processed run prefix with:

```bash
export FLEET_ARTIFACT_BASE_URI="$(terraform output -raw dashboard_artifact_base_uri)"
```

For Lambda-backed pipeline execution, also set:

```bash
export FLEET_PIPELINE_EXECUTION_MODE="lambda"
export FLEET_RAW_UPLOAD_BASE_URI="$(terraform output -raw dashboard_raw_upload_base_uri)"
```

The dashboard currently writes and reads this run layout under the configured artifact base URI:

```text
s3://bucket/processed/runs/{run_id}/input.csv
s3://bucket/processed/runs/{run_id}/recommendations.parquet
s3://bucket/processed/runs/{run_id}/summary.json
```

Dashboard uploads use a separate raw upload prefix:

```text
s3://bucket/raw/uploads/{run_id}/input.csv
```

## Pipeline Lambda

The pipeline Lambda runs as a container image because the pipeline depends on pandas and pyarrow. Terraform also manages its CloudWatch log group with seven-day retention, so `terraform destroy` removes the function logs with the rest of the stack. After the initial Terraform apply creates the ECR repository, build and push the image:

Install/start Docker Desktop first if `docker --version` is not available.

```bash
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REPOSITORY_URL="$(terraform output -raw pipeline_lambda_repository_url)"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker build -f ../../Dockerfile.lambda -t fleet-strategy-pipeline-lambda ../..
docker tag fleet-strategy-pipeline-lambda:latest "$REPOSITORY_URL:latest"
docker push "$REPOSITORY_URL:latest"
```

On Docker Desktop/buildx, Lambda may reject images pushed as OCI manifest lists with provenance attestations. This command builds and pushes a Lambda-compatible ARM64 image directly:

```bash
docker buildx build --platform linux/arm64 --provenance=false \
  -f ../../Dockerfile.lambda \
  -t "$REPOSITORY_URL:latest" \
  --push ../..
```

Then apply Terraform again with the image URI to create the Lambda and S3 trigger:

```bash
terraform apply -var="lambda_image_uri=${REPOSITORY_URL}:latest"
```

After that, uploads to:

```text
s3://bucket/raw/uploads/{run_id}/input.csv
```

trigger Lambda to write:

```text
s3://bucket/processed/runs/{run_id}/recommendations.parquet
s3://bucket/processed/runs/{run_id}/summary.json
```

## Dashboard Hosting

The dashboard deployment uses ECS Express Mode through `aws_ecs_express_gateway_service`. Express Mode manages the public load balancer, HTTPS endpoint, target groups, service security group, and autoscaling resources around the dashboard container. Terraform still manages the ECR repository, ECS cluster, CloudWatch log group, IAM task execution role, IAM infrastructure role, and IAM task role.

Create the optional Gemini key as a free-tier-friendly SSM Parameter Store standard SecureString:

```bash
aws ssm put-parameter \
  --name "/fleet-strategy-engine/dev/google-api-key" \
  --type SecureString \
  --value "YOUR_GEMINI_API_KEY" \
  --overwrite
```

Build and push the dashboard image for the Fargate platform used by ECS Express:

```bash
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
DASHBOARD_REPOSITORY_URL="$(terraform output -raw dashboard_repository_url)"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

docker buildx build --platform linux/amd64 \
  -f ../../Dockerfile.dashboard \
  -t "${DASHBOARD_REPOSITORY_URL}:latest" \
  --push ../..
```

Use the pushed image digest for the dashboard deployment. This avoids mutable-tag drift and ensures ECS deploys the exact image you just pushed.

```bash
PIPELINE_REPOSITORY_URL="$(terraform output -raw pipeline_lambda_repository_url)"
DASHBOARD_IMAGE_DIGEST="$(aws ecr describe-images \
  --repository-name fleet-strategy-engine-dev-dashboard \
  --image-ids imageTag=latest \
  --query 'imageDetails[0].imageDigest' \
  --output text)"

terraform apply \
  -var="lambda_image_uri=${PIPELINE_REPOSITORY_URL}:latest" \
  -var="dashboard_image_uri=${DASHBOARD_REPOSITORY_URL}@${DASHBOARD_IMAGE_DIGEST}" \
  -var="google_api_key_parameter_name=/fleet-strategy-engine/dev/google-api-key"
```

After deployment, get the public dashboard URL:

```bash
terraform output -raw dashboard_url
```

The deployed dashboard runs with Lambda-backed pipeline execution and reads/writes the same S3 artifact layout used by local S3 mode.
