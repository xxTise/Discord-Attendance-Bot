# Pro Clubs Daily Check-In Bot

A Discord bot that runs a daily availability check-in for a competitive EA FC Pro Clubs
team: posts a check-in board each day, collects position-based availability
(GK / Defense / Midfield / Offense, or Out), locks responses before kickoff, and sends
automatic pre-kickoff reminders. Deployed 24/7 on AWS EC2.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the architecture and build plan,
[DEPLOY.md](DEPLOY.md) for hosting, and [docs/ANALYTICS.md](docs/ANALYTICS.md) for the
S3 + Athena attendance-analytics pipeline.

## Features

- Daily auto-posted check-in board, updated live and grouped by position
- Position-based responses: GK / Defense / Midfield / Offense, or Out
- Automatic locking a configurable window before kickoff, plus captain manual lock/unlock
- Pre-kickoff announcements (lobby-up, now-locked) and non-responder reminders
- Full response history persisted for attendance analytics

## Analytics

Attendance data feeds a two-layer design (operational vs. analytical):

- **Operational (in-app):** an `/attendance` report in Discord for quick roster decisions
  — reliable regulars, chronically unavailable, and non-participants. *(planned)*
- **Analytical (AWS):** response data is exported to an **S3** data lake and queried with
  **Amazon Athena** (SQL) using an EC2 IAM instance role for credential-less access.
  *(implemented — see [docs/ANALYTICS.md](docs/ANALYTICS.md))*

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## Configuration

Copy `.env.example` to `.env` and fill in the values. Captain-only actions
(lock / unlock / change event type / set kickoff time) are gated on the Discord
**Administrator** permission or a configurable captain role.

## Deployment

Runs on a single AWS EC2 (Ubuntu) instance under `systemd`. See [DEPLOY.md](DEPLOY.md).
