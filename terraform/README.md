# Terraform — reproducible environment (not the live bot)

This configuration does **not** manage the live production resources
(`i-023f692c20923f6c0`, security group `sg-0579ad59651df99f8`, IAM role
`proclubs-ec2-s3`). Those were created by hand in the console and stay that
way deliberately — nothing here has been `terraform import`-ed, and running
`terraform apply` cannot modify or destroy them.

Instead, this models an equivalent, reproducible environment: everything is
prefixed `${var.environment}-` (default `demo`), so it never collides with
the live resource names even though it deploys into the same AWS account and
default VPC. Think of it as "how would I stand this up again" made concrete
and diffable, not a live ops tool.

## Usage

```bash
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: your admin IP, an existing key pair name, your email

terraform init
terraform validate
terraform plan
# terraform apply   # only if you actually want a second environment running
```

Creating the key pair referenced by `key_pair_name` (out of band — Terraform
deliberately doesn't generate one, see `variables.tf`):

```bash
aws ec2 create-key-pair --key-name pro-clubs-bot-demo \
  --query 'KeyMaterial' --output text > pro-clubs-bot-demo.pem
chmod 400 pro-clubs-bot-demo.pem
```

## State

Local state (`terraform.tfstate`, gitignored), on purpose — single operator,
not shared infrastructure. If this were real multi-person infra, the answer
would be an S3 backend with native locking:

```hcl
# backend "s3" {
#   bucket       = "proclubs-terraform-state"
#   key          = "demo/terraform.tfstate"
#   region       = "us-east-1"
#   use_lockfile = true   # native S3 locking, Terraform >= 1.10
#   encrypt      = true
# }
```

Not implemented here — there's no second operator to coordinate with, so it
would be pure ceremony.
