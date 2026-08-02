data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# --- Security group: SSH from admin IP only, all egress ---

resource "aws_security_group" "bot" {
  name        = "${var.environment}-proclubs-bot-sg"
  description = "Discord bot instance - SSH from admin IP only, all egress"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "SSH from admin IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }

  egress {
    description = "All outbound (Discord API, apt, AWS APIs)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.environment}-proclubs-bot-sg" })
}

# --- IAM: EC2 instance role, scoped S3 policy, CloudWatch Agent, SSM ---

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "bot_instance_role" {
  name               = "${var.environment}-proclubs-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  tags               = var.tags
}

# Scoped S3 access matching the live proclubs-ec2-s3 role's documented
# intent (docs/ANALYTICS.md): list + read/write objects, nothing else, on
# exactly one bucket. NOTE: verify this against the real policy JSON once
# audited (see Section 0 of the implementation plan) and correct if it drifts.
data "aws_iam_policy_document" "s3_analytics_access" {
  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${var.s3_bucket_name}"]
  }
  statement {
    sid       = "ReadWriteObjects"
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["arn:aws:s3:::${var.s3_bucket_name}/*"]
  }
}

resource "aws_iam_role_policy" "s3_analytics" {
  name   = "${var.environment}-proclubs-s3-analytics"
  role   = aws_iam_role.bot_instance_role.id
  policy = data.aws_iam_policy_document.s3_analytics_access.json
}

# CloudWatch Agent needs PutMetricData/CreateLogGroup etc. to publish the
# custom process/memory metrics used by the alarms below.
resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.bot_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# Required for the GitHub Actions deploy workflow to reach this instance
# via SSM Run Command instead of SSH (see .github/workflows/ci-cd.yml).
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.bot_instance_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "bot" {
  name = "${var.environment}-proclubs-ec2-profile"
  role = aws_iam_role.bot_instance_role.name
  tags = var.tags
}

# --- EC2 instance ---

resource "aws_instance" "bot" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.default.ids[0]
  vpc_security_group_ids = [aws_security_group.bot.id]
  iam_instance_profile   = aws_iam_instance_profile.bot.name
  key_name               = var.key_pair_name

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
  }

  metadata_options {
    # Enforce IMDSv2. Deliberate hardening — the live instance may not
    # currently require this; treat bringing it in line as a follow-up,
    # not something to silently skip here.
    http_tokens = "required"
  }

  tags = merge(var.tags, { Name = "${var.environment}-discord-attendance-bot" })
}

# --- Monitoring: CloudWatch Agent-backed alarms + SNS ---

resource "aws_sns_topic" "alerts" {
  name = "${var.environment}-proclubs-alerts"
  tags = var.tags
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
  # Stays "PendingConfirmation" until the recipient clicks the email link —
  # Terraform can't complete that step. Verify with:
  # aws sns list-subscriptions-by-topic --topic-arn <arn>
}

# Process-down detection. Requires the CloudWatch Agent's procstat plugin
# (see the agent config in docs, applied to the live box) — EC2 has no
# native "is this process running" metric, and systemd's Restart=always
# means a crash-looping bot would never trip a plain instance-status alarm.
resource "aws_cloudwatch_metric_alarm" "bot_process_down" {
  alarm_name          = "${var.environment}-proclubs-process-down"
  alarm_description   = "Bot process (main.py) is not running on the instance"
  namespace           = "ProClubsBot"
  metric_name         = "procstat_lookup_pid_count"
  dimensions = {
    InstanceId = aws_instance.bot.id
    pattern    = "Discord-Attendance-Bot/main.py"
  }
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 2
  datapoints_to_alarm = 2
  threshold           = 1
  comparison_operator = "LessThanThreshold"
  # The agent going silent (e.g. instance down) should also page, not go quiet.
  treat_missing_data = "breaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}

# EC2 doesn't expose memory as a native AWS/EC2 metric — this is why the
# CloudWatch Agent (mem_used_percent) is required for memory alerting.
resource "aws_cloudwatch_metric_alarm" "bot_memory_high" {
  alarm_name          = "${var.environment}-proclubs-memory-high"
  alarm_description   = "Memory usage above 85% for 5 minutes on a 1GB t2.micro"
  namespace           = "ProClubsBot"
  metric_name         = "mem_used_percent"
  dimensions          = { InstanceId = aws_instance.bot.id }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = 85
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "missing"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "cpu_high" {
  alarm_name          = "${var.environment}-proclubs-cpu-high"
  alarm_description   = "CPU above 80% for 5 minutes"
  namespace           = "AWS/EC2"
  metric_name         = "CPUUtilization"
  dimensions          = { InstanceId = aws_instance.bot.id }
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = 80
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "missing"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}
