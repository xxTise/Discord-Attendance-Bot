"""Unit tests for Athena result parsing (no real AWS calls)."""

from __future__ import annotations

from services import analytics_service


def _cell(value: str) -> dict:
    return {"VarCharValue": value}


class _FakePaginator:
    def __init__(self, pages: list[dict]) -> None:
        self._pages = pages

    def paginate(self, **_kwargs):
        return self._pages


class _FakeClient:
    def __init__(self, pages: list[dict]) -> None:
        self._paginator = _FakePaginator(pages)

    def get_paginator(self, name: str):
        assert name == "get_query_results"
        return self._paginator


def test_parse_rows_skips_header_row():
    pages = [
        {
            "ResultSet": {
                "Rows": [
                    {"Data": [_cell("display_name"), _cell("events_responded"),
                               _cell("times_available"), _cell("availability_pct")]},
                    {"Data": [_cell("Ava"), _cell("10"), _cell("8"), _cell("80.0")]},
                ]
            }
        }
    ]
    rows = analytics_service._parse_rows(_FakeClient(pages), "qid")
    assert len(rows) == 1
    assert rows[0].display_name == "Ava"
    assert rows[0].events_responded == 10
    assert rows[0].times_available == 8
    assert rows[0].availability_pct == 80.0


def test_parse_rows_header_skipped_only_once_across_pages():
    pages = [
        {"ResultSet": {"Rows": [
            {"Data": [_cell("display_name"), _cell("events_responded"),
                       _cell("times_available"), _cell("availability_pct")]},
            {"Data": [_cell("Ava"), _cell("10"), _cell("8"), _cell("80.0")]},
        ]}},
        {"ResultSet": {"Rows": [
            {"Data": [_cell("Ben"), _cell("10"), _cell("2"), _cell("20.0")]},
        ]}},
    ]
    rows = analytics_service._parse_rows(_FakeClient(pages), "qid")
    assert [r.display_name for r in rows] == ["Ava", "Ben"]
