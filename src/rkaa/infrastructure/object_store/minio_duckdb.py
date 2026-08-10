from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import duckdb


@dataclass(frozen=True)
class MinioDuckDBConfig:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    extension_directory: str | None = None
    region: str = "us-east-1"
    url_style: str = "path"
    use_ssl: bool = False


def load_minio_config_from_env() -> MinioDuckDBConfig:
    endpoint = os.getenv("MINIO_ENDPOINT")
    access_key = os.getenv("MINIO_KEY") or os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET") or os.getenv("MINIO_SECRET_KEY")
    bucket = os.getenv("MINIO_BUCKET")
    extension_directory = os.getenv("MINIO_EXT_DIR") or os.getcwd()

    missing = []
    if not endpoint:
        missing.append("MINIO_ENDPOINT")
    if not access_key:
        missing.append("MINIO_KEY or MINIO_ACCESS_KEY")
    if not secret_key:
        missing.append("MINIO_SECRET or MINIO_SECRET_KEY")
    if not bucket:
        missing.append("MINIO_BUCKET")

    if missing:
        raise RuntimeError(f"Missing MinIO config: {missing}")

    return MinioDuckDBConfig(
        endpoint=endpoint,
        access_key=access_key,
        secret_key=secret_key,
        bucket=bucket,
        extension_directory=extension_directory,
    )


def create_minio_duckdb_connection(config: MinioDuckDBConfig) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect()

    if config.extension_directory:
        ext_dir = str(Path(config.extension_directory).resolve())
        conn.execute(f"SET extension_directory='{ext_dir}'")

    conn.execute("LOAD httpfs")

    conn.execute(
        """
        CREATE OR REPLACE SECRET minio_secret (
            TYPE s3,
            KEY_ID ?,
            SECRET ?,
            ENDPOINT ?,
            URL_STYLE 'path',
            REGION ?,
            USE_SSL false
        )
        """,
        [
            config.access_key,
            config.secret_key,
            config.endpoint,
            config.region,
        ],
    )

    return conn
