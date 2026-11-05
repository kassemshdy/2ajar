from enum import StrEnum

from sqlalchemy import Enum as SAEnum


def enum_type[E: StrEnum](enum_cls: type[E], name: str) -> SAEnum:
    """Portable enum stored as VARCHAR + CHECK constraint (easier to evolve than native PG enums)."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [m.value for m in members],
        validate_strings=True,
    )
