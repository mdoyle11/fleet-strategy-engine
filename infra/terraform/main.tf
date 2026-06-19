provider "aws" {
  region = var.aws_region
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_s3_bucket" "artifacts" {
  bucket_prefix = "${local.name_prefix}-artifacts-"
  force_destroy = true

  tags = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    id     = "expire-raw-uploads"
    status = "Enabled"

    filter {
      prefix = "raw/uploads/"
    }

    expiration {
      days = var.raw_upload_expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  rule {
    id     = "expire-processed-runs"
    status = "Enabled"

    filter {
      prefix = "processed/runs/"
    }

    expiration {
      days = var.processed_run_expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }
}

resource "aws_ecr_repository" "pipeline_lambda" {
  name                 = "${local.name_prefix}-pipeline-lambda"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_ecr_lifecycle_policy" "pipeline_lambda" {
  repository = aws_ecr_repository.pipeline_lambda.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the most recent ${var.ecr_max_images} images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.ecr_max_images
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_iam_role" "pipeline_lambda" {
  name = "${local.name_prefix}-pipeline-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "pipeline_lambda_basic" {
  role       = aws_iam_role.pipeline_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "pipeline_lambda_s3" {
  name = "${local.name_prefix}-pipeline-lambda-s3"
  role = aws_iam_role.pipeline_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.artifacts.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = aws_s3_bucket.artifacts.arn
      }
    ]
  })
}

resource "aws_cloudwatch_log_group" "pipeline_lambda" {
  count = var.lambda_image_uri == "" ? 0 : 1

  name              = "/aws/lambda/${local.name_prefix}-pipeline"
  retention_in_days = 7

  tags = local.common_tags
}

resource "aws_lambda_function" "pipeline" {
  count = var.lambda_image_uri == "" ? 0 : 1

  function_name = "${local.name_prefix}-pipeline"
  package_type  = "Image"
  image_uri     = var.lambda_image_uri
  role          = aws_iam_role.pipeline_lambda.arn
  architectures = ["arm64"]
  timeout       = 120
  memory_size   = 1024

  environment {
    variables = {
      FLEET_PROCESSED_BASE_URI = "s3://${aws_s3_bucket.artifacts.bucket}/processed/runs"
      FLEET_RAW_UPLOAD_PREFIX  = "raw/uploads/"
    }
  }

  tags = local.common_tags

  depends_on = [
    aws_cloudwatch_log_group.pipeline_lambda,
    aws_iam_role_policy_attachment.pipeline_lambda_basic,
    aws_iam_role_policy.pipeline_lambda_s3,
  ]
}

resource "aws_lambda_permission" "allow_s3_pipeline_invoke" {
  count = var.lambda_image_uri == "" ? 0 : 1

  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pipeline[0].function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.artifacts.arn
}

resource "aws_s3_bucket_notification" "pipeline_uploads" {
  count = var.lambda_image_uri == "" ? 0 : 1

  bucket = aws_s3_bucket.artifacts.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.pipeline[0].arn
    events              = ["s3:ObjectCreated:Put"]
    filter_prefix       = "raw/uploads/"
    filter_suffix       = "input.csv"
  }

  depends_on = [aws_lambda_permission.allow_s3_pipeline_invoke]
}
