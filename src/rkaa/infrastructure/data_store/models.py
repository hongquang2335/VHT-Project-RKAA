from dataclasses import dataclass


@dataclass(frozen=True)
class KPIRecord:
    timestamp: str
    period_end: str
    ne_id: str
    cell_id: str
    kpi_name: str
    value: float
    unit: str
    quality_flag: str
