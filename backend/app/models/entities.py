"""Transport-independent document records and exact Firestore value conversion."""

import json
from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4
from backend.app.database.query import Field


def utcnow():
    return datetime.now(timezone.utc)


class Record:
    def __init__(self, **values):
        unexpected = set(values) - set(self.fields)
        if unexpected:
            raise ValueError(f"Unexpected record fields: {unexpected}")
        for name, spec in self.fields.items():
            default = spec["default"]
            if default == "__uuid__":
                default = uuid4()
            elif default == "__now__":
                default = utcnow()
            elif default == "__list__":
                default = []
            elif default == "__dict__":
                default = {}
            setattr(self, name, values.get(name, deepcopy(default)))

    def document(self):
        data = {}
        for name, spec in self.fields.items():
            value = getattr(self, name)
            if value is not None:
                if spec["type"] == "CHAR(32)":
                    value = str(value)
                elif spec["type"] == "DATE":
                    value = value.isoformat()
                elif name == "hours":
                    value = int(Decimal(str(value)) * 100)
            data[name] = value
        return data

    @classmethod
    def from_document(cls, data):
        values = {}
        for name, spec in cls.fields.items():
            value = data.get(name)
            if value is not None:
                if spec["type"] == "CHAR(32)":
                    value = UUID(value)
                elif spec["type"] == "DATE":
                    value = date.fromisoformat(value)
                elif name == "hours":
                    value = Decimal(value) / 100
            values[name] = value
        return cls(**values)


SCHEMA = json.loads(Path(__file__).with_name("schema.json").read_text())
MODELS = []
for _name, _spec in SCHEMA.items():
    _model = type(_name, (Record,), {"collection": _spec["collection"], "fields": _spec["fields"]})
    for _field in _model.fields:
        setattr(_model, _field, Field(_model, _field))
    globals()[_name] = _model
    MODELS.append(_model)
