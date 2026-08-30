from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def d(obj: Any) -> dict[str, Any]:
    return obj.to_dict()


def dl(rows) -> list[dict[str, Any]]:
    return [r.to_dict() for r in rows]


def get_or_404(db, model, id_: str):
    obj = db.get(model, id_)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {id_} not found")
    return obj
