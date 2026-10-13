"""Small document-query vocabulary; no SQL or SQLAlchemy dependency.

Firestore narrows candidates with one single-field index. Remaining predicates,
substring search, ordering and exact totals are evaluated on authorized candidates.
This deliberately targets the small portfolio dataset, not unbounded analytics.
"""

import re
from dataclasses import dataclass


@dataclass(eq=False)
class Predicate:
    field: object
    op: str
    value: object

    def matches(self, obj, db):
        left = getattr(obj, self.field.name)
        right = list(db.scalars(self.value)) if isinstance(self.value, Query) else self.value
        if self.op == "in":
            return left in right
        if self.op == "like":
            pattern = "".join(
                ".*" if c == "%" else "." if c == "_" else re.escape(c) for c in right
            )
            return re.fullmatch(pattern, left or "", re.IGNORECASE) is not None
        if self.op == "==":
            return left == right
        if self.op == "!=":
            return left != right
        if left is None or right is None:
            return False
        return {
            ">": lambda: left > right,
            ">=": lambda: left >= right,
            "<": lambda: left < right,
            "<=": lambda: left <= right,
        }[self.op]()


@dataclass
class Either:
    predicates: tuple

    def matches(self, obj, db):
        return any(p.matches(obj, db) for p in self.predicates)


class Field:
    def __init__(self, model, name):
        self.model, self.name = model, name

    def __get__(self, instance, owner):
        return instance.__dict__.get(self.name) if instance is not None else self

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value

    def __eq__(self, other):
        return Predicate(self, "==", other)

    def __ne__(self, other):
        return Predicate(self, "!=", other)

    def __gt__(self, other):
        return Predicate(self, ">", other)

    def __ge__(self, other):
        return Predicate(self, ">=", other)

    def __lt__(self, other):
        return Predicate(self, "<", other)

    def __le__(self, other):
        return Predicate(self, "<=", other)

    def in_(self, other):
        return Predicate(self, "in", other)

    def is_(self, other):
        return self == other

    def ilike(self, other):
        return Predicate(self, "like", other)

    def desc(self):
        return (self, True)


@dataclass
class Aggregate:
    kind: str
    field: object = None
    fallback: object = None


class Functions:
    def count(self):
        return Aggregate("count")

    def sum(self, field):
        return Aggregate("sum", field)

    def coalesce(self, aggregate, fallback):
        aggregate.fallback = fallback
        return aggregate


func = Functions()


class Query:
    def __init__(self, target):
        self.target = target
        self.model = (
            target.model
            if isinstance(target, Field)
            else target.field.model
            if isinstance(target, Aggregate) and target.field
            else target
            if isinstance(target, type)
            else None
        )
        self.predicates, self.orders = [], []
        self.maximum, self.skip, self.source = None, 0, None

    def where(self, *predicates):
        self.predicates.extend(predicates)
        if self.model is None and predicates:
            self.model = predicates[0].field.model
        return self

    def order_by(self, *fields):
        self.orders.extend(fields)
        return self

    def limit(self, value):
        self.maximum = value
        return self

    def offset(self, value):
        self.skip = value
        return self

    def with_for_update(self):
        # Every transactional read is tracked by Firestore; actor guards cover absence queries.
        return self

    def subquery(self):
        return self

    def select_from(self, source):
        if isinstance(source, Query):
            self.source, self.model = source, source.model
        else:
            self.model = source
        return self


def select(target):
    return Query(target)


def or_(*predicates):
    return Either(predicates)


class Delete(Query):
    pass


def delete(model):
    return Delete(model)
