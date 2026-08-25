from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(frozen=True)
class CollectionConfig:
    parquet_prefix: str = "v3/*.parquet"
    granularity_minutes: int = 5
    datetime_column: str = "datetime"
    ne_column: str = "ne"
    cellname_column: str = "cellname"
    default_limit: int | None = None
    output_path: str = "tmp/minio_kpi_long.csv"


def load_collection_config(path: str | Path = "configs/config.yaml") -> CollectionConfig:
    p = Path(path)
    if not p.exists():
        return CollectionConfig()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    m = data.get("minio", {})
    c = data.get("collection", {})
    return CollectionConfig(
        parquet_prefix=str(m.get("parquet_prefix", "v3/*.parquet")),
        granularity_minutes=int(c.get("granularity_minutes", 5)),
        datetime_column=str(c.get("datetime_column", "datetime")),
        ne_column=str(c.get("ne_column", "ne")),
        cellname_column=str(c.get("cellname_column", "cellname")),
        default_limit=(
            None
            if c.get("default_limit") is None
            else int(c.get("default_limit"))
        ),
        output_path=str(c.get("output_path", "tmp/minio_kpi_long.csv")),
    )
