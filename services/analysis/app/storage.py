import json
from functools import cache
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import S3_ACCESS_KEY, S3_BUCKET, S3_ENDPOINT, S3_SECRET_KEY

STEMS = ("vocals", "drums", "bass", "other")


@cache
def _client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


# Mesmas chaves que o serviço de separação grava.
def input_key(sha: str) -> str:
    return f"inputs/{sha}.wav"


def stem_keys(sha: str) -> dict[str, str]:
    return {stem: f"stems/{sha}/{stem}.wav" for stem in STEMS}


def analysis_key(sha: str) -> str:
    return f"analysis/{sha}.json"


def exists(key: str) -> bool:
    try:
        _client().head_object(Bucket=S3_BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def download(key: str, path: Path) -> None:
    _client().download_file(S3_BUCKET, key, str(path))


def get_json(key: str) -> dict | None:
    try:
        body = _client().get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    return json.loads(body)


def put_json(key: str, data: dict) -> None:
    _client().put_object(
        Bucket=S3_BUCKET, Key=key, Body=json.dumps(data).encode(), ContentType="application/json"
    )
