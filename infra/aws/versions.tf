terraform {
  required_version = ">= 1.12.0, < 2.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region              = "us-east-1"
  profile             = "investmind"
  allowed_account_ids = ["990861495140"]

  default_tags {
    tags = {
      Project     = "InvestMindAI"
      Environment = "demo"
      ManagedBy   = "Terraform"
    }
  }
}
