"""Repository for Baseline persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from rkaa.core.exceptions import NotFoundError
from rkaa.infrastructure.data_store.models.baseline import Baseline


class BaselineRepository:
    """CRUD operations for persisted KPI baselines."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, baseline: Baseline) -> Baseline:
        existing = self._find_existing(
            ne_id=baseline.ne_id,
            kpi_name=baseline.kpi_name,
            day_period=baseline.day_period,
            week_profile=baseline.week_profile,
        )
        if existing is None:
            self._session.add(baseline)
            self._session.flush()
            self._session.refresh(baseline)
            return baseline

        for field_name in (
            "mean_value",
            "median_value",
            "std_value",
            "p5_value",
            "p95_value",
            "sample_count",
            "clean_day_count",
            "required_day_count",
            "confidence_status",
            "computed_at",
        ):
            setattr(existing, field_name, getattr(baseline, field_name))

        self._session.flush()
        self._session.refresh(existing)
        return existing

    def get_by_key(
        self,
        *,
        ne_id: str,
        kpi_name: str,
        day_period: str,
        week_profile: str,
    ) -> Baseline:
        baseline = self._find_existing(
            ne_id=ne_id,
            kpi_name=kpi_name,
            day_period=day_period,
            week_profile=week_profile,
        )
        if baseline is None:
            raise NotFoundError(
                "Baseline "
                f"'{ne_id}/{kpi_name}/{day_period}/{week_profile}' not found."
            )
        return baseline

    def list_by_ne_kpi(self, *, ne_id: str, kpi_name: str) -> list[Baseline]:
        statement = (
            select(Baseline)
            .where(Baseline.ne_id == ne_id)
            .where(Baseline.kpi_name == kpi_name)
            .order_by(Baseline.week_profile, Baseline.day_period, Baseline.id)
        )
        return list(self._session.scalars(statement))

    def delete(
        self,
        *,
        ne_id: str,
        kpi_name: str,
        day_period: str,
        week_profile: str,
    ) -> None:
        baseline = self.get_by_key(
            ne_id=ne_id,
            kpi_name=kpi_name,
            day_period=day_period,
            week_profile=week_profile,
        )
        self._session.delete(baseline)
        self._session.flush()

    def _find_existing(
        self,
        *,
        ne_id: str,
        kpi_name: str,
        day_period: str,
        week_profile: str,
    ) -> Baseline | None:
        statement = (
            select(Baseline)
            .where(Baseline.ne_id == ne_id)
            .where(Baseline.kpi_name == kpi_name)
            .where(Baseline.day_period == day_period)
            .where(Baseline.week_profile == week_profile)
        )
        return self._session.scalar(statement)
