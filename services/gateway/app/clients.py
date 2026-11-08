from functools import cache

import boto3
import httpx
import redis
from botocore.config import Config

from app.config import REDIS_URL, S3_ACCESS_KEY, S3_ENDPOINT, S3_SECRET_KEY


@cache
def http() -> httpx.Client:
    return httpx.Client(timeout=60)


@cache
def store() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL)


@cache
def s3():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )
