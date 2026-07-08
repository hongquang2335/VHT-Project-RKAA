"""Input schemas for KPI data collection."""

from __future__ import annotations

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)


class InputSchemaError(ValueError):
    """Raised when raw KPI input data does not satisfy the contract."""


class KPIInputRow(BaseModel):
    """Validated representation of one KPI CSV row."""

    model_config = ConfigDict(extra="forbid")

    timestamp: AwareDatetime
    period_end: AwareDatetime
    ne_id: str
    kpi_name: str
    value: float
    unit: str
    quality_flag: str

    @field_validator("ne_id", "kpi_name")
    @classmethod
    def validate_non_empty_identifier(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_time_window(self) -> "KPIInputRow":
        if self.period_end <= self.timestamp:
            raise ValueError("period_end must be greater than timestamp")
        return self


def validate_kpi_input_row(payload: dict[str, object]) -> KPIInputRow:
    """Validate one raw KPI input payload against the CSV contract."""

    try:
        return KPIInputRow.model_validate(payload)
    except ValidationError as exc:
        raise InputSchemaError(str(exc)) from exc
