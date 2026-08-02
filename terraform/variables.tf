variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name, prefixed onto every resource name/tag so this never collides with the hand-created live resources (proclubs-bot-sg, proclubs-ec2-s3, etc)."
  type        = string
  default     = "demo"
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t2.micro"
}

variable "ami_id" {
  description = "Ubuntu 24.04 LTS AMI for the chosen region (default is us-east-1's, matching the live instance)."
  type        = string
  default     = "ami-0f8a61b66d1accaee"
}

variable "key_pair_name" {
  description = "Name of an EXISTING EC2 key pair. Terraform does not generate key material here — an aws_key_pair/tls_private_key resource would write the private key into terraform.tfstate in plaintext, which is a well-known anti-pattern. Create the key pair out of band first: aws ec2 create-key-pair --key-name <name> --query 'KeyMaterial' --output text > <name>.pem"
  type        = string
}

variable "admin_cidr" {
  description = "CIDR allowed to SSH into the instance, e.g. 203.0.113.5/32. Must be a specific address, not 0.0.0.0/0 (see the live sg-0579ad59651df99f8 finding this project fixed)."
  type        = string

  validation {
    condition     = var.admin_cidr != "0.0.0.0/0"
    error_message = "admin_cidr must not be 0.0.0.0/0."
  }
}

variable "s3_bucket_name" {
  description = "S3 bucket the instance role gets scoped read/write access to (attendance analytics data lake)."
  type        = string
  default     = "proclubs-analytics-to-demo"
}

variable "alert_email" {
  description = "Receives CloudWatch alarm notifications via SNS. Requires manual confirmation via the email link after apply — Terraform cannot complete that step."
  type        = string
}

variable "tags" {
  description = "Common tags applied to every resource."
  type        = map(string)
  default = {
    Project   = "pro-clubs-checkin-bot"
    ManagedBy = "terraform"
  }
}
