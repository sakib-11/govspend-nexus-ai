# Terraform configuration for GovSpend Nexus AI
# For AWS/GCP/Azure cloud deployment

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.9"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC
resource "aws_vpc" "govspend" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name        = "govspend-vpc"
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

# Subnets
resource "aws_subnet" "private" {
  count             = length(var.availability_zones)
  vpc_id            = aws_vpc.govspend.id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = var.availability_zones[count.index]
  
  tags = {
    Name        = "govspend-private-${count.index + 1}"
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

# EKS Cluster
resource "aws_eks_cluster" "govspend" {
  name     = "govspend-eks"
  version  = "1.28"
  role_arn = aws_iam_role.eks_master.arn
  
  vpc_config {
    subnet_ids = aws_subnet.private[*].id
  }
  
  tags = {
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "govspend" {
  identifier     = "govspend-postgres"
  engine         = "postgres"
  engine_version = "15.3"
  instance_class = "db.t3.medium"
  
  allocated_storage     = 50
  max_allocated_storage = 100
  storage_encrypted     = true
  
  db_name  = "govspend"
  username = var.db_username
  password = var.db_password
  
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.govspend.name
  
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"
  
  skip_final_snapshot = var.environment == "development"
  
  tags = {
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "govspend" {
  cluster_id           = "govspend-redis"
  engine              = "redis"
  node_type           = "cache.t3.micro"
  num_cache_nodes     = 1
  parameter_group_name = "default.redis7"
  port                = 6379
  
  subnet_group_name = aws_elasticache_subnet_group.govspend.name
  security_group_ids = [aws_security_group.redis.id]
  
  tags = {
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

# KMS Key for encryption
resource "aws_kms_key" "govspend" {
  description             = "KMS key for GovSpend Nexus AI"
  deletion_window_in_days = 30
  enable_key_rotation    = true
  
  tags = {
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

# S3 Bucket for backups
resource "aws_s3_bucket" "govspend" {
  bucket = "govspend-nexus-${var.environment}-${data.aws_caller_identity.current.account_id}"
  
  tags = {
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

# Security Groups
resource "aws_security_group" "rds" {
  name        = "govspend-rds-sg"
  description = "Security group for RDS"
  vpc_id      = aws_vpc.govspend.id
  
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes.id]
  }
  
  tags = {
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

resource "aws_security_group" "redis" {
  name        = "govspend-redis-sg"
  description = "Security group for Redis"
  vpc_id      = aws_vpc.govspend.id
  
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.eks_nodes.id]
  }
  
  tags = {
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

resource "aws_security_group" "eks_nodes" {
  name        = "govspend-eks-nodes-sg"
  description = "Security group for EKS nodes"
  vpc_id      = aws_vpc.govspend.id
  
  ingress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    self      = true
  }
  
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = {
    Environment = var.environment
    Project     = "govspend-nexus"
  }
}

# Outputs
output "eks_cluster_name" {
  value = aws_eks_cluster.govspend.name
}

output "rds_endpoint" {
  value = aws_db_instance.govspend.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.govspend.cache_nodes[0].address
}

output "kms_key_id" {
  value = aws_kms_key.govspend.id
}

output "s3_bucket" {
  value = aws_s3_bucket.govspend.bucket
}
