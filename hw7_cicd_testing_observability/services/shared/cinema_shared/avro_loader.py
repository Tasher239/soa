from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=4)
def load_avro_schema(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Avro schema not found at {path}")
    return p.read_text(encoding="utf-8")
