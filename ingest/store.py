"""Object storage for raw regulator documents.

Two implementations behind one protocol:
  * R2Store    — Cloudflare R2 via the S3-compatible API. Production.
  * LocalStore — filesystem. Tests and local development, so the pipeline can be
                 exercised end to end without credentials.

The bucket is private and is never served to end users (brief §11.3). We store raw
documents so we can re-parse historical versions when the parser improves, and so a
diff can always be reproduced from source — which is what makes the audit trail real.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def object_key(regulator_code: str, instrument_ref: str, sha: str, suffix: str) -> str:
    """Content-addressed key: identical bytes always land on the same key.

    Keyed by hash rather than by date or version number, so re-fetching an unchanged
    document overwrites itself harmlessly instead of accumulating duplicates.
    """
    safe_ref = instrument_ref.replace("/", "-").replace(" ", "_")
    return f"{regulator_code}/{safe_ref}/{sha}{suffix}"


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def get(self, key: str) -> bytes: ...


class LocalStore:
    """Filesystem-backed store for tests and local runs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / key

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()


class R2Store:
    """Cloudflare R2 over the S3-compatible API.

    Credentials come from the environment (GitHub Actions secrets in CI); they are
    never read from a file in the repo.
    """

    def __init__(
        self,
        account_id: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        bucket: str | None = None,
    ) -> None:
        import boto3  # imported lazily so tests need no AWS SDK

        self.bucket = bucket or os.environ["R2_BUCKET"]
        account = account_id or os.environ["R2_ACCOUNT_ID"]
        self._client = boto3.client(
            "s3",
            endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id or os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=secret_access_key or os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )

    def get(self, key: str) -> bytes:
        return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        return True

    def usage(self) -> tuple[int, int]:
        """(object count, total bytes) across the whole bucket.

        Paginated: list_objects_v2 returns at most 1000 keys per call, and the corpus
        already has more than that once every version's raw PDF is stored. Used by the
        weekly cost report (§13) to watch R2 against the 10 GB free-tier ceiling.
        """
        count = total = 0
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket):
            for obj in page.get("Contents", []):
                count += 1
                total += obj["Size"]
        return count, total
