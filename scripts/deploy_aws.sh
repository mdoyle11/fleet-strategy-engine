#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT_DIR}/infra/terraform"
TFVARS_FILE="${TF_DIR}/terraform.tfvars"

for command in aws docker terraform uv; do
  if ! command -v "${command}" >/dev/null 2>&1; then
    echo "Required command not found: ${command}" >&2
    exit 1
  fi
done

if [[ ! -f "${TFVARS_FILE}" ]]; then
  echo "Missing ${TFVARS_FILE}" >&2
  echo "Create it with:" >&2
  echo "  cp ${TF_DIR}/terraform.tfvars.example ${TFVARS_FILE}" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop and retry." >&2
  exit 1
fi

echo "Initializing Terraform..."
terraform -chdir="${TF_DIR}" init

TF_REGION="$(terraform -chdir="${TF_DIR}" console <<< "var.aws_region" | tr -d '"[:space:]')"
export AWS_REGION="${AWS_REGION:-${TF_REGION}}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"

echo "Verifying AWS credentials..."
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
echo "Deploying to AWS account ${AWS_ACCOUNT_ID} in ${AWS_REGION}."

if [[ "${SKIP_TESTS:-0}" != "1" ]]; then
  echo "Running tests..."
  (cd "${ROOT_DIR}" && uv run pytest)
fi

if ! LAMBDA_REPOSITORY_URL="$(terraform -chdir="${TF_DIR}" output -raw pipeline_lambda_repository_url 2>/dev/null)" ||
  ! DASHBOARD_REPOSITORY_URL="$(terraform -chdir="${TF_DIR}" output -raw dashboard_repository_url 2>/dev/null)" ||
  [[ -z "${LAMBDA_REPOSITORY_URL}" || -z "${DASHBOARD_REPOSITORY_URL}" ]]; then
  echo "Creating base infrastructure..."
  terraform -chdir="${TF_DIR}" apply \
    -var="lambda_image_uri=" \
    -var="dashboard_image_uri="

  LAMBDA_REPOSITORY_URL="$(terraform -chdir="${TF_DIR}" output -raw pipeline_lambda_repository_url)"
  DASHBOARD_REPOSITORY_URL="$(terraform -chdir="${TF_DIR}" output -raw dashboard_repository_url)"
fi

echo "Authenticating Docker with ECR..."
aws ecr get-login-password --region "${AWS_REGION}" |
  docker login \
    --username AWS \
    --password-stdin \
    "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

GIT_REVISION="$(git -C "${ROOT_DIR}" rev-parse --short HEAD 2>/dev/null || echo no-git)"
DEPLOY_TAG="${DEPLOY_TAG:-$(date -u +%Y%m%d%H%M%S)-${GIT_REVISION}}"

echo "Building and pushing Lambda image ${DEPLOY_TAG}..."
docker buildx build \
  --platform linux/arm64 \
  --provenance=false \
  -f "${ROOT_DIR}/Dockerfile.lambda" \
  -t "${LAMBDA_REPOSITORY_URL}:${DEPLOY_TAG}" \
  --push \
  "${ROOT_DIR}"

echo "Building and pushing dashboard image ${DEPLOY_TAG}..."
docker buildx build \
  --platform linux/amd64 \
  -f "${ROOT_DIR}/Dockerfile.dashboard" \
  -t "${DASHBOARD_REPOSITORY_URL}:${DEPLOY_TAG}" \
  --push \
  "${ROOT_DIR}"

LAMBDA_REPOSITORY_NAME="${LAMBDA_REPOSITORY_URL#*/}"
DASHBOARD_REPOSITORY_NAME="${DASHBOARD_REPOSITORY_URL#*/}"

LAMBDA_DIGEST="$(aws ecr describe-images \
  --repository-name "${LAMBDA_REPOSITORY_NAME}" \
  --image-ids "imageTag=${DEPLOY_TAG}" \
  --query "imageDetails[0].imageDigest" \
  --output text \
  --region "${AWS_REGION}")"

DASHBOARD_DIGEST="$(aws ecr describe-images \
  --repository-name "${DASHBOARD_REPOSITORY_NAME}" \
  --image-ids "imageTag=${DEPLOY_TAG}" \
  --query "imageDetails[0].imageDigest" \
  --output text \
  --region "${AWS_REGION}")"

LAMBDA_IMAGE_URI="${LAMBDA_REPOSITORY_URL}@${LAMBDA_DIGEST}"
DASHBOARD_IMAGE_URI="${DASHBOARD_REPOSITORY_URL}@${DASHBOARD_DIGEST}"

echo "Deploying Lambda and dashboard..."
terraform -chdir="${TF_DIR}" apply \
  -var="lambda_image_uri=${LAMBDA_IMAGE_URI}" \
  -var="dashboard_image_uri=${DASHBOARD_IMAGE_URI}"

echo
echo "Deployment complete."
echo "Dashboard URL: $(terraform -chdir="${TF_DIR}" output -raw dashboard_url)"
echo "Lambda image: ${LAMBDA_IMAGE_URI}"
echo "Dashboard image: ${DASHBOARD_IMAGE_URI}"
