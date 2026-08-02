terraform {
  required_version = ">= 1.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Local state on purpose: this config does not manage shared or live
  # infrastructure (see README.md), and has a single operator. See
  # README.md for the S3 remote-backend pattern this would use for real
  # multi-person infra.
  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region
}
