# Pro Clubs Daily Check-In Bot

A Discord bot that runs a daily availability check-in for a competitive EA FC Pro Clubs
team: posts a check-in embed each day, collects Available / Out responses, locks
responses before kickoff, and sends automatic kickoff reminders.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the architecture and build plan.

## Status

Phase 1 in progress. Increment 1 (database + core service layer) is implemented and tested.
The Discord runtime layer (views, cogs, scheduler) is next.

## Development

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

## Configuration

Copy `.env.example` to `.env` and fill in the values. Captain-only actions
(lock / unlock / change event type) are gated on the Discord **Administrator** permission.
