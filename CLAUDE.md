# CLAUDE.md

## Project Overview

Pro Clubs Daily Check-In Bot for Discord.

Purpose:
Manage player availability, attendance tracking, lineup selection, reminders, and inactivity monitoring for a competitive EA FC Pro Clubs team.

## Tech Stack

* Python 3.12+
* discord.py
* SQLAlchemy ORM
* SQLite (initially)
* APScheduler
* dotenv

## Core Principles

1. Use service-layer architecture.
2. Business logic must not live inside Discord command handlers.
3. Database access must go through repositories/services.
4. Use type hints everywhere.
5. Use async patterns when interacting with Discord.
6. Keep modules small and focused.
7. Write maintainable code over clever code.
8. Do not introduce unnecessary dependencies.

## Folder Responsibilities

cogs/

* Slash commands
* Discord event handlers
* UI interactions

services/

* Attendance logic
* Lineup logic
* Locking logic
* Reminder logic

database/

* Models
* Database initialization
* Queries

views/

* Buttons
* Modals
* Embeds

scheduler/

* Scheduled jobs

## Features

### Daily Check-In

* Auto-post every day at 12:00 PM CT.
* Default event type: Practice.
* Captain may change event type to Match.
* Embed updates live.

### Responses

Available
Unavailable
Late

Late responses must capture ETA.

Users may edit responses until lock.

### Locking

Events lock automatically at configured deadline.
Only captains may manually lock/unlock.
Responses become read-only after lock.

### Attendance

Track all responses historically.
Track streaks.
Track missed check-ins.
Track attendance percentage.

### Lineups

Captain selects starting lineup.
Remaining available players become reserves.

### Reminders

Notify users who have not responded.
Support both DM and channel reminders.

## Code Quality Rules

* Use dataclasses or Pydantic where appropriate.
* Avoid duplicate logic.
* Use enums for response states.
* Add logging to all critical actions.
* Handle Discord API failures gracefully.
* Include docstrings for public methods.

## Execution Priority

1. Working bot > perfect architecture
2. Each phase must be fully functional before moving on
3. Avoid over-engineering early abstractions
4. Prefer simple implementations that can evolve

## Future Roadmap

Phase 1

* Core attendance system
* Reminders
* Locking

Phase 2

* Lineups
* Statistics
* Inactivity reports

Phase 3

* PostgreSQL
* Multi-team support
* Web dashboard
* AWS deployment
