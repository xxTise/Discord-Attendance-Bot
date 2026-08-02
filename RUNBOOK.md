# Runbook — Pro Clubs Discord Bot

Quick reference for checking health, restarting, and rolling back. For full
hosting/setup details see [DEPLOY.md](DEPLOY.md).

## Check health

```bash
sudo systemctl status proclubs
journalctl -u proclubs -n 100 --no-pager
journalctl -u proclubs -f                 # live tail
```

On the server, with the real `.env` in place:

```bash
.venv/bin/python -m scripts.login_check   # confirms token, guild, channel, synced slash commands
.venv/bin/python -m scripts.perm_check    # confirms the bot's Discord channel permissions
```

Alarms (once Section 3 monitoring is live — see the implementation plan):

```bash
aws cloudwatch describe-alarms \
  --alarm-names proclubs-process-down proclubs-memory-high proclubs-cpu-high \
  --region us-east-1
```

## Restart

```bash
sudo systemctl restart proclubs && sudo systemctl status proclubs
```

## Roll back a bad deploy

The GitHub Actions deploy workflow deploys an exact commit
(`git reset --hard $GITHUB_SHA`, not a loose `git pull`), so rollback is
always "reset to the previous known-good SHA."

1. Find the last-known-good commit:
   ```bash
   git log --oneline -10
   ```
2. On the server directly:
   ```bash
   cd /home/ubuntu/Discord-Attendance-Bot
   git fetch origin
   git reset --hard <good-sha>
   .venv/bin/pip install -q -r requirements.txt
   sudo systemctl restart proclubs
   ```
3. Or from your laptop, no SSH needed (same path the deploy workflow uses):
   ```bash
   aws ssm send-command --instance-ids i-023f692c20923f6c0 \
     --document-name AWS-RunShellScript \
     --parameters 'commands=["cd /home/ubuntu/Discord-Attendance-Bot","git reset --hard <good-sha>",".venv/bin/pip install -q -r requirements.txt","systemctl restart proclubs"]' \
     --region us-east-1
   ```
4. Verify: `journalctl -u proclubs -n 50`, then re-run `scripts.login_check`.

No separate tagging scheme is needed for this single-branch, single-deployer
project — `git log` is the source of truth for "what was last known good."
If this ever grows multi-deployer, switch to `git tag deploy-<date> <sha>`
per release for a clearer audit trail.

## Manually restart the CloudWatch Agent (if metrics stop flowing)

```bash
sudo systemctl restart amazon-cloudwatch-agent
sudo systemctl status amazon-cloudwatch-agent
aws cloudwatch list-metrics --namespace ProClubsBot --region us-east-1
```
