"""Athena query execution for the weekly attendance report.

Queries the S3+Athena analytics pipeline (see docs/ANALYTICS.md) — a
separate, periodically-exported copy of attendance data, not the bot's own
live SQLite database. boto3 is synchronous, so every AWS call here runs in
a thread via :func:`fetch_attendance_report` to avoid blocking the bot's
event loop.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import boto3

_ATTENDANCE_QUERY = """
SELECT display_name,
       COUNT(*) AS events_responded,
       SUM(CASE WHEN state = 'AVAILABLE' THEN 1 ELSE 0 END) AS times_available,
       ROUND(100.0 * SUM(CASE WHEN state = 'AVAILABLE' THEN 1 ELSE 0 END) / COUNT(*), 1) AS availability_pct
FROM responses
GROUP BY display_name
ORDER BY availability_pct DESC
""".strip()

_POLL_INTERVAL_SECONDS = 2
_MAX_POLLS = 30  # ~1 minute ceiling before giving up


class AthenaQueryError(Exception):
    """Raised when the Athena query fails, is cancelled, or times out."""


@dataclass
class AttendanceRow:
    """One player's attendance-rate row from the query."""

    display_name: str
    events_responded: int
    times_available: int
    availability_pct: float


def _parse_rows(client, query_id: str) -> list[AttendanceRow]:
    """Fetch and parse query results, skipping the one header row Athena returns."""
    rows: list[AttendanceRow] = []
    skip_header = True
    for page in client.get_paginator("get_query_results").paginate(QueryExecutionId=query_id):
        for row in page["ResultSet"]["Rows"]:
            if skip_header:
                skip_header = False
                continue
            values = [field.get("VarCharValue", "") for field in row["Data"]]
            rows.append(
                AttendanceRow(
                    display_name=values[0],
                    events_responded=int(values[1]),
                    times_available=int(values[2]),
                    availability_pct=float(values[3]),
                )
            )
    return rows


def _run_query_sync(*, region: str, database: str, output_location: str) -> list[AttendanceRow]:
    """Blocking start/poll/fetch cycle. Only call this from a worker thread."""
    client = boto3.client("athena", region_name=region)

    start = client.start_query_execution(
        QueryString=_ATTENDANCE_QUERY,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": output_location},
    )
    query_id = start["QueryExecutionId"]

    for _ in range(_MAX_POLLS):
        execution = client.get_query_execution(QueryExecutionId=query_id)
        state = execution["QueryExecution"]["Status"]["State"]
        if state == "SUCCEEDED":
            return _parse_rows(client, query_id)
        if state in ("FAILED", "CANCELLED"):
            reason = execution["QueryExecution"]["Status"].get("StateChangeReason", state)
            raise AthenaQueryError(f"Athena query {state.lower()}: {reason}")
        time.sleep(_POLL_INTERVAL_SECONDS)

    client.stop_query_execution(QueryExecutionId=query_id)
    raise AthenaQueryError("Athena query timed out waiting for results")


async def fetch_attendance_report(
    *, region: str, database: str, output_location: str
) -> list[AttendanceRow]:
    """Run the attendance-rate-per-player query and return ranked rows."""
    return await asyncio.to_thread(
        _run_query_sync, region=region, database=database, output_location=output_location
    )
