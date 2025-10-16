"""Utility helpers."""
from __future__ import annotations

from bson import ObjectId


def to_object_id(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise ValueError(f"Invalid ObjectId: {value}")
    return ObjectId(value)


def object_id_str(value: ObjectId) -> str:
    return str(value)
