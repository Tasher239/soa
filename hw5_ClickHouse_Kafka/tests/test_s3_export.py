from __future__ import annotations

import io
from datetime import date

import aioboto3
import httpx
import pyarrow.parquet as pq
import pytest
from botocore.config import Config

from tests.helpers import (
    AGGREGATOR_URL,
    S3_ACCESS_KEY,
    S3_BUCKET,
    S3_ENDPOINT,
    S3_SECRET_KEY,
)


async def _s3_head_and_get(key: str):
    session = aioboto3.Session(
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
    )
    cfg = Config(signature_version="s3v4", retries={"max_attempts": 5})
    async with session.client("s3", endpoint_url=S3_ENDPOINT, config=cfg) as s3:
        head = await s3.head_object(Bucket=S3_BUCKET, Key=key)
        obj = await s3.get_object(Bucket=S3_BUCKET, Key=key)
        body = await obj["Body"].read()
        return head, body


@pytest.mark.asyncio
async def test_export_writes_parquet_and_is_idempotent():
    today = date.today().isoformat()
    key = f"daily/{today}/aggregates.parquet"

    async with httpx.AsyncClient(timeout=60) as client:
        await client.post(f"{AGGREGATOR_URL}/aggregate?date={today}")

        r1 = await client.post(f"{AGGREGATOR_URL}/export?date={today}")
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["bucket"] == S3_BUCKET
        assert body1["key"] == key

        head1, payload1 = await _s3_head_and_get(key)
        assert head1["ContentLength"] > 0

        tbl = pq.read_table(io.BytesIO(payload1))
        assert tbl.num_rows > 0
        assert set(tbl.schema.names) >= {"metric_date", "metric_name", "metric_value"}

        r2 = await client.post(f"{AGGREGATOR_URL}/export?date={today}")
        assert r2.status_code == 200, r2.text
        head2, _ = await _s3_head_and_get(key)
        assert head2["ContentLength"] > 0
        assert head2["LastModified"] >= head1["LastModified"]
