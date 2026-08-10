from __future__ import annotations
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rkaa.infrastructure.object_store.minio_duckdb import (
    create_minio_duckdb_connection,
    load_minio_config_from_env,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret-file", default="secrets/minio.local")
    parser.add_argument("--parquet-prefix", default="v3/*.parquet")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    secret_path = ROOT_DIR / args.secret_file
    if secret_path.exists():
        load_dotenv(secret_path)

    config = load_minio_config_from_env()
    conn = create_minio_duckdb_connection(config)
    uri = f"s3://{config.bucket}/{args.parquet_prefix}"
    df = conn.execute(f"SELECT * FROM read_parquet('{uri}') LIMIT {int(args.limit)}").df()
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist())
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
