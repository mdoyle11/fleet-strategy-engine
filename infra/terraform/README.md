# Terraform

This is the initial AWS foundation for the fleet strategy deployment. It creates the S3 artifact bucket that holds raw uploads and processed pipeline outputs. It also creates an ECR repository for the pipeline Lambda container image.

The default retention settings are intentionally small for local MVP use:

- ECR keeps the latest 2 container images.
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

When the upload-triggered pipeline is added, raw uploads should use a separate prefix:

```text
s3://bucket/raw/uploads/{run_id}/input.csv
```

## Pipeline Lambda

The pipeline Lambda runs as a container image because the pipeline depends on pandas and pyarrow. After the initial Terraform apply creates the ECR repository, build and push the image:

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

ECS hosting, latest-run manifests, and stricter least-privilege IAM can be added after this Lambda path is verified.
