data "aws_caller_identity" "current" {}

data "aws_partition" "current" {}

data "aws_region" "current" {}

locals {
  deploy_dashboard       = var.dashboard_image_uri != ""
  dashboard_name         = "${local.name_prefix}-dashboard"
  dashboard_service_name = "${local.dashboard_name}-express"
  dashboard_port         = 8501
  google_api_key_parameter_arn = var.google_api_key_parameter_name == "" ? "" : (
    "arn:${data.aws_partition.current.partition}:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter${var.google_api_key_parameter_name}"
  )
}

resource "aws_ecr_repository" "dashboard" {
  name                 = "${local.name_prefix}-dashboard"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}

resource "aws_ecr_lifecycle_policy" "dashboard" {
  repository = aws_ecr_repository.dashboard.name

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

resource "aws_cloudwatch_log_group" "dashboard" {
  count = local.deploy_dashboard ? 1 : 0

  name              = "/ecs/${local.dashboard_name}"
  retention_in_days = 7

  tags = local.common_tags
}

resource "aws_ecs_cluster" "dashboard" {
  count = local.deploy_dashboard ? 1 : 0

  name = local.dashboard_name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }

  tags = local.common_tags
}

resource "aws_iam_role" "dashboard_execution" {
  count = local.deploy_dashboard ? 1 : 0

  name = "${local.dashboard_name}-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "dashboard_execution" {
  count = local.deploy_dashboard ? 1 : 0

  role       = aws_iam_role.dashboard_execution[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "dashboard_execution_ssm" {
  count = local.deploy_dashboard && var.google_api_key_parameter_name != "" ? 1 : 0

  name = "${local.dashboard_name}-ssm"
  role = aws_iam_role.dashboard_execution[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = local.google_api_key_parameter_arn
      }
    ]
  })
}

resource "aws_iam_role" "dashboard_task" {
  count = local.deploy_dashboard ? 1 : 0

  name = "${local.dashboard_name}-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "dashboard_task_s3" {
  count = local.deploy_dashboard ? 1 : 0

  name = "${local.dashboard_name}-s3"
  role = aws_iam_role.dashboard_task[0].id

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

resource "aws_iam_role" "dashboard_infrastructure" {
  count = local.deploy_dashboard ? 1 : 0

  name = "${local.dashboard_name}-infra"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "dashboard_infrastructure" {
  count = local.deploy_dashboard ? 1 : 0

  role       = aws_iam_role.dashboard_infrastructure[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSInfrastructureRoleforExpressGatewayServices"
}

resource "aws_ecs_express_gateway_service" "dashboard" {
  count = local.deploy_dashboard ? 1 : 0

  service_name            = local.dashboard_service_name
  cluster                 = aws_ecs_cluster.dashboard[0].id
  cpu                     = tostring(var.dashboard_cpu)
  memory                  = tostring(var.dashboard_memory)
  execution_role_arn      = aws_iam_role.dashboard_execution[0].arn
  infrastructure_role_arn = aws_iam_role.dashboard_infrastructure[0].arn
  task_role_arn           = aws_iam_role.dashboard_task[0].arn
  health_check_path       = "/_stcore/health"
  wait_for_steady_state   = true

  scaling_target = [
    {
      min_task_count            = var.dashboard_min_capacity
      max_task_count            = var.dashboard_max_capacity
      auto_scaling_metric       = "AVERAGE_CPU"
      auto_scaling_target_value = 70
    }
  ]

  primary_container {
    image          = var.dashboard_image_uri
    container_port = local.dashboard_port

    aws_logs_configuration = [
      {
        log_group         = aws_cloudwatch_log_group.dashboard[0].name
        log_stream_prefix = "dashboard"
      }
    ]

    environment {
      name  = "FLEET_PIPELINE_EXECUTION_MODE"
      value = "lambda"
    }

    environment {
      name  = "FLEET_ARTIFACT_BASE_URI"
      value = "s3://${aws_s3_bucket.artifacts.bucket}/processed/runs"
    }

    environment {
      name  = "FLEET_RAW_UPLOAD_BASE_URI"
      value = "s3://${aws_s3_bucket.artifacts.bucket}/raw/uploads"
    }

    environment {
      name  = "FLEET_PIPELINE_WAIT_SECONDS"
      value = "90"
    }

    environment {
      name  = "GEMINI_MODEL"
      value = var.gemini_model
    }

    dynamic "secret" {
      for_each = var.google_api_key_parameter_name == "" ? [] : [local.google_api_key_parameter_arn]

      content {
        name       = "GOOGLE_API_KEY"
        value_from = secret.value
      }
    }
  }

  tags = local.common_tags

  depends_on = [
    aws_iam_role_policy_attachment.dashboard_execution,
    aws_iam_role_policy_attachment.dashboard_infrastructure,
    aws_iam_role_policy.dashboard_execution_ssm,
    aws_iam_role_policy.dashboard_task_s3,
  ]
}
