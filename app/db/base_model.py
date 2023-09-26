from datetime import datetime, timezone
from typing import Optional

import sqlmodel
from sqlalchemy import DateTime, TypeDecorator
from sqlmodel import Field, SQLModel


def get_utc_now():
    return datetime.now(timezone.utc)


class TZDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class BaseDBModel(SQLModel):
    id: Optional[int] = Field(primary_key=True, index=True)
    created: datetime | None = Field(
        default_factory=get_utc_now,
        sa_column=sqlmodel.Column(
            TZDateTime,
        ),
    )
    updated: datetime | None = Field(
        default_factory=get_utc_now,
        sa_column=sqlmodel.Column(
            TZDateTime,
            onupdate=get_utc_now,
        ),
    )
