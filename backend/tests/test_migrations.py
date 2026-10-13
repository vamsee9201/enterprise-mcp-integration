from datetime import date
from decimal import Decimal
from uuid import uuid4
from backend.app.models.entities import TimeEntry


def test_firestore_hours_and_dates_roundtrip():
    entry = TimeEntry(
        timesheet_id=uuid4(),
        project_id=uuid4(),
        work_date=date(2026, 10, 12),
        hours=Decimal("7.35"),
        description="",
    )
    document = entry.document()
    assert document["hours"] == 735
    assert document["work_date"] == "2026-10-12"
    result = TimeEntry.from_document(document)
    assert result.hours == Decimal("7.35")
    assert result.id == entry.id
