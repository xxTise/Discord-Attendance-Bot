# Deployment — Single EC2 Ubuntu Instance (Free Tier)

The simplest, lowest-cost way to run this bot 24/7: one small EC2 instance, Ubuntu,
systemd to keep it alive, SQLite on the instance's disk. No ECS, Kubernetes, RDS,
Terraform, or Docker.

**Why this is cheap and simple:** the bot only makes *outbound* connections to
Discord. It serves no traffic, so there is no load balancer, no inbound web port,
and no database server — SQLite is a file on disk.

This document describes the live instance, created by hand in the console. For a
reproducible version of the same setup (EC2 + security group + IAM role) that can
stand up a *second* environment from scratch, see [`terraform/`](terraform/). For
day-2 operations (health checks, restart, rollback) see
[`RUNBOOK.md`](RUNBOOK.md).

---

## 0. Cost summary

| Item | Choice | Cost |
|---|---|---|
| Compute | `t3.micro` (or `t2.micro`) — 1 vCPU, 1 GB RAM | **Free** for 12 months (750 hrs/mo), then ~$7.50/mo |
| Storage | 8 GB gp3 EBS | Free (within 30 GB free tier), then ~$0.64/mo |
| Data transfer | Outbound to Discord only, tiny | Effectively free |
| Database | SQLite file on EBS | $0 |

After the 12-month free tier, the cheapest option is an ARM `t4g.nano`/`t4g.micro`
(~$3–7/mo). The steps below work on both x86 (`t3.micro`) and ARM (`t4g.*`) because
all Python deps ship prebuilt wheels for both.

---

## 1. EC2 setup

1. **Console → EC2 → Launch instance.**
2. **Name:** `discord-attendance-bot`
3. **AMI:** *Ubuntu Server 24.04 LTS* (free-tier eligible). Ships Python 3.12.
4. **Instance type:** `t3.micro` (or `t2.micro`). Both are free-tier eligible.
5. **Key pair:** Create a new key pair (`pro-clubs-bot`), type `.pem`, and download it.
   This is how you SSH in — keep it safe.
6. **Storage:** 8 GB gp3 (default). Leave "Delete on termination" checked, but note
   that means terminating the instance deletes your SQLite DB — see §6 for backups.
7. **Network / Auto-assign public IP:** Enabled.
8. Configure the security group as in §2, then **Launch**.

> Optional but recommended: after launch, allocate an **Elastic IP** and associate it
> so the public IP doesn't change if you stop/start the instance.

---

## 2. Security groups

The bot needs **no inbound ports** except SSH for you to manage it.

**Inbound rules:**

| Type | Protocol | Port | Source |
|---|---|---|---|
| SSH | TCP | 22 | **My IP** (your home/office IP only) |

**Outbound rules:** leave the default *Allow all* (the bot must reach Discord on 443).

That's it. No HTTP/HTTPS inbound, no database port. Restricting SSH to *My IP* keeps
the box effectively invisible.

> **History:** this security group was found with SSH also open to `0.0.0.0/0`
> (in addition to the admin IP) — an unintentional exposure from manual console
> setup, since fixed. It's exactly the kind of drift that infrastructure-as-code
> (see `terraform/`) makes visible in a diff instead of silently accumulating.

---

## 3. Connect & Python environment setup

SSH in (from the folder holding your `.pem`):

```bash
chmod 400 pro-clubs-bot.pem
ssh -i pro-clubs-bot.pem ubuntu@<EC2_PUBLIC_IP>
```

Install system packages (Python 3.12 is already present on Ubuntu 24.04):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip git tzdata
```

Clone the repo and create the virtual environment:

```bash
cd ~
git clone https://github.com/xxTise/Discord-Attendance-Bot.git
cd Discord-Attendance-Bot
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Create the `.env` file (this lives only on the server — it is gitignored and never
pulled). Use an **absolute** `DATABASE_URL` so the DB location is stable regardless of
working directory:

```bash
nano .env
```

```dotenv
DISCORD_TOKEN=your-real-bot-token
GUILD_ID=000000000000000000
CHECKIN_CHANNEL_ID=000000000000000000
CAPTAIN_ROLE_ID=000000000000000000

TIMEZONE=America/Chicago
TIMEZONE_LABEL=CT
CHECKIN_TIME=12:00
EVENT_TIME=19:00
LOCK_OFFSET_MINUTES=60

DATABASE_URL=sqlite+aiosqlite:////home/ubuntu/Discord-Attendance-Bot/proclubs.db
```

> Note the **four** slashes in `sqlite+aiosqlite:////home/...` — three for the URL
> scheme plus the leading `/` of the absolute path.

Test it runs in the foreground before installing the service:

```bash
.venv/bin/python main.py
# Expect: "Logged in as Dictator#2695". Ctrl+C to stop.
```

Confirm the server clock is synced (the scheduler depends on it — this is on by
default on Ubuntu):

```bash
timedatectl   # look for "System clock synchronized: yes"
```

---

## 4. GitHub deployment workflow

`.env` and `proclubs.db` are gitignored, so updates never overwrite your secrets or
data. Two options — start with A.

### Option A — Manual pull (simplest; recommended)

Create a deploy script on the server:

```bash
nano ~/Discord-Attendance-Bot/deploy.sh
```

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /home/ubuntu/Discord-Attendance-Bot
git pull --ff-only
.venv/bin/pip install -q -r requirements.txt
sudo systemctl restart proclubs
echo "Deployed: $(git rev-parse --short HEAD)"
```

```bash
chmod +x ~/Discord-Attendance-Bot/deploy.sh
```

To ship a new version: push to GitHub from your laptop, then on the server run
`./deploy.sh`.

### Option B — Auto-deploy on push (GitHub Actions, implemented)

Implemented at `.github/workflows/ci-cd.yml`: on every push/PR it runs the 28-test
suite; on push to `main` (only if tests passed) it deploys automatically.

**This deliberately does not use SSH.** An earlier draft of this doc (see git
history) suggested `appleboy/ssh-action`, but GitHub-hosted runners have no fixed
IP — making that work means either opening port 22 to `0.0.0.0/0` (undoing the
"SSH from My IP only" rule in §2) or babysitting GitHub's rotating IP ranges as a
security-group allowlist. Neither is worth it.

Instead, the deploy job authenticates to AWS via **GitHub OIDC** (no stored AWS
keys — just a role ARN, which isn't secret) and runs the deploy commands through
**AWS Systems Manager Run Command**, which needs zero inbound ports at all:

- One-time AWS setup: a GitHub OIDC identity provider + an IAM role
  (`github-actions-deploy-proclubs`) trusted only for
  `repo:xxTise/Discord-Attendance-Bot:ref:refs/heads/main`, scoped to
  `ssm:SendCommand`/`ssm:GetCommandInvocation` on this one instance. The instance's
  own role (`proclubs-ec2-s3`) needs `AmazonSSMManagedInstanceCore` attached so SSM
  can reach it.
- Repo config: **Settings → Secrets and variables → Actions → Variables** (not
  Secrets — none of these are sensitive): `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`,
  `EC2_INSTANCE_ID`.
- Since SSM Run Command executes as root by default, the sudoers NOPASSWD
  workaround in §5 (needed for password-less `systemctl restart` over SSH) isn't
  needed for this path.

Manual `./deploy.sh` (Option A) still works and is the right choice if you ever
need to deploy from a box that isn't CI.

---

## 5. systemd service (auto-start on boot, auto-restart on crash)

```bash
sudo nano /etc/systemd/system/proclubs.service
```

```ini
[Unit]
Description=Pro Clubs Discord Attendance Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Discord-Attendance-Bot
ExecStart=/home/ubuntu/Discord-Attendance-Bot/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`WorkingDirectory` is the project root, so the app finds `.env` there. Enable and
start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable proclubs     # start automatically after every reboot
sudo systemctl start proclubs
sudo systemctl status proclubs     # should show "active (running)"
```

Not needed for the implemented Option B (SSM Run Command executes as root
already). Only relevant if you ever automate a restart over plain SSH instead —
in that case, let the `ubuntu` user restart the service without a password:

```bash
echo 'ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart proclubs' | \
  sudo tee /etc/sudoers.d/proclubs
```

---

## 6. SQLite persistence

- The database is a single file: `proclubs.db` in the project directory (set to an
  absolute path in `.env`, §3). It is created automatically on first run.
- **It survives reboots and stop/start** because it lives on the EBS volume.
- `git pull` never touches it (gitignored).
- **It is deleted only if you terminate the instance** (EBS delete-on-termination), so
  take periodic backups.

Simple daily backup with cron (keeps copies in `~/backups`):

```bash
mkdir -p ~/backups
crontab -e
```

```cron
# 03:00 server time: snapshot the SQLite DB, keep 14 days
0 3 * * * sqlite3 /home/ubuntu/Discord-Attendance-Bot/proclubs.db ".backup '/home/ubuntu/backups/proclubs-$(date +\%F).db'" && find /home/ubuntu/backups -name 'proclubs-*.db' -mtime +14 -delete
```

(`sqlite3 .backup` is safe to run while the bot is live. Install it with
`sudo apt install -y sqlite3` if needed.) To copy a backup to your laptop:

```bash
scp -i pro-clubs-bot.pem ubuntu@<EC2_PUBLIC_IP>:~/backups/proclubs-YYYY-MM-DD.db .
```

---

## 7. Logging & troubleshooting

The app logs to stdout/stderr, which systemd captures in the journal — no log files
to manage.

```bash
# Live logs (follow)
journalctl -u proclubs -f

# Last 200 lines
journalctl -u proclubs -n 200 --no-pager

# Logs since a time
journalctl -u proclubs --since "1 hour ago"

# Service state / restart / stop
sudo systemctl status proclubs
sudo systemctl restart proclubs
sudo systemctl stop proclubs
```

**Common issues**

| Symptom | Likely cause | Fix |
|---|---|---|
| `SystemExit: DISCORD_TOKEN is not set` | `.env` missing or in the wrong dir | Ensure `.env` is in `WorkingDirectory`; check `cat .env` |
| `LoginFailure: Improper token` | Wrong/rotated token | Update `DISCORD_TOKEN` in `.env`, `systemctl restart proclubs` |
| `PrivilegedIntentsRequired` | Server Members Intent off | Enable it in the Discord Developer Portal → Bot |
| Bot online but pings fire at wrong time | Clock drift | `timedatectl` → ensure "synchronized: yes" (`systemd-timesyncd`) |
| Service keeps restarting | Crash on startup | `journalctl -u proclubs -n 100` to read the traceback |
| DB "disappeared" after redeploy | Relative `DATABASE_URL` + different CWD | Use the absolute `DATABASE_URL` from §3 |
| Can't SSH | Security group / wrong IP | Confirm SG allows your current IP on 22 |

**Memory note:** on `t3.micro`/`t2.micro` (1 GB) this bot uses well under 150 MB.
If you ever drop to a 512 MB instance and see OOM kills, add 1 GB swap:

```bash
sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 8. Monitoring & alerting (CloudWatch Agent)

`systemd`'s `Restart=always` means a crash-looping bot never shows up in plain
EC2 status/CPU metrics — and EC2 doesn't expose memory as a native metric at
all. Real "is the process actually alive" and memory monitoring needs the
CloudWatch Agent installed on the box, publishing custom metrics that three
CloudWatch Alarms watch (process down, memory high, CPU high — SNS emails you
on any of them). See the implementation plan / `terraform/main.tf` for the
alarm definitions (same thresholds are used for the live instance's manually
created alarms, since Terraform here doesn't manage the live box — see
`terraform/README.md`).

```bash
# on the instance, after the role has CloudWatchAgentServerPolicy attached
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb

sudo nano /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
# paste the ProClubsBot config (mem_used_percent, disk used_percent, procstat
# on "Discord-Attendance-Bot/main.py") — see implementation plan Section 3

sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
sudo systemctl enable amazon-cloudwatch-agent

aws cloudwatch list-metrics --namespace ProClubsBot --region us-east-1   # verify
```

---

## Quick reference — first deploy, in order

```bash
# on the EC2 box
sudo apt update && sudo apt install -y python3-venv python3-pip git tzdata sqlite3
git clone https://github.com/xxTise/Discord-Attendance-Bot.git
cd Discord-Attendance-Bot
python3 -m venv .venv && .venv/bin/pip install -U pip && .venv/bin/pip install -r requirements.txt
nano .env                      # paste secrets (see §3)
.venv/bin/python main.py       # smoke test, then Ctrl+C
sudo nano /etc/systemd/system/proclubs.service   # paste unit (see §5)
sudo systemctl daemon-reload && sudo systemctl enable --now proclubs
journalctl -u proclubs -f      # watch it log in
```

## Stopping costs

To pause billing without losing anything, **Stop** (not Terminate) the instance from
the console — EBS (and your DB) persist; you only pay the tiny EBS cost. Terminating
deletes the volume.
