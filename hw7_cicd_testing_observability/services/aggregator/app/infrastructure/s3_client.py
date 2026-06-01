from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import aioboto3
from botocore.config import Config

from app.core.config import settings


@asynccontextmanager
async def s3_client() -> AsyncIterator:
    session = aioboto3.Session(
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
    )
    cfg = Config(
        retries={"max_attempts": 5, "mode": "adaptive"},
        signature_version="s3v4",
    )
    async with session.client(
        "s3", endpoint_url=settings.s3_endpoint, config=cfg
    ) as client:
        yield client
