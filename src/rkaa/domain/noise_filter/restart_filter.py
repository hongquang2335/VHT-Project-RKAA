"""Bước 3 FR-201: phát hiện counter reset và suy ra NE restart.

Luồng xử lý:
1. Chỉ xét các cumulative counter được khai báo trong ``eligible_metrics``.
2. Tìm điểm counter giảm mạnh về vùng giá trị nhỏ -> ``CounterResetEvidence``.
3. Kiểm tra một vài điểm sau reset có tăng trở lại để xác nhận reset không phải nhiễu.
4. Gom các counter reset gần cùng thời điểm trên cùng NE.
5. Chỉ suy ra ``NE_RESTART`` khi số counter đồng thời đạt ``min_concurrent_counters``.
6. Loại dữ liệu của NE trong khoảng từ thời điểm restart đến hết ``post_restart_grace_minutes``.

Lưu ý:
- Filter này KHÔNG coi KPI = 0 là NE restart.
- Nếu không có cumulative counter phù hợp thì filter tự bỏ qua.
- File chỉ xử lý DataFrame trong bộ nhớ, không sửa dữ liệu nguồn trên MinIO.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from rkaa.domain.noise_filter.models import FilterOutcome, RestartConfig
from rkaa.domain.noise_filter.utils import parse_timestamp_series, require_columns, split_by_mask


@dataclass(frozen=True, slots=True)
class CounterResetEvidence:
    """Bằng chứng cho một lần reset của MỘT counter trên một NE.

    Mỗi evidence thuộc đúng một chuỗi ``ne_id + cell_id + metric_name``.
    ``previous_value`` là giá trị trước reset, ``current_value`` là giá trị sau khi
    giảm mạnh, còn ``drop_ratio`` là tỷ lệ giảm so với giá trị trước đó.
    """

    ne_id: str
    cell_id: str
    metric_name: str
    timestamp: pd.Timestamp
    previous_value: float
    current_value: float
    drop_ratio: float


@dataclass(frozen=True, slots=True)
class RestartEvent:
    """Một NE restart đã được suy ra từ nhiều counter reset gần cùng thời điểm."""

    ne_id: str
    timestamp: pd.Timestamp
    metrics: tuple[str, ...]


class RestartFilter:
    """Phát hiện counter reset và tạo exclusion window cho NE restart."""

    def __init__(self, config: RestartConfig) -> None:
        # Toàn bộ ngưỡng phát hiện được lấy từ config để có thể bật/tắt hoặc tune
        # mà không phải sửa logic trong file này.
        self.config = config

    def _confirm_candidate(self, values: list[float], index: int) -> bool:
        """Xác nhận counter thật sự reset bằng cách nhìn các điểm sau candidate.

        Ví dụ: ``152000 -> 30 -> 750 -> 1600``.
        Nếu ``30`` là candidate và các điểm sau không giảm, đồng thời giá trị cuối
        lớn hơn ``30``, candidate được xác nhận là counter đã bắt đầu tích lũy lại.
        """

        required = self.config.confirmation_points
        if required <= 0:
            return True

        # Cần đủ ``required`` điểm phía sau candidate để xác nhận.
        end = index + required
        if end >= len(values):
            return False

        # Bao gồm cả candidate tại ``index`` và các điểm xác nhận phía sau.
        sequence = values[index : end + 1]
        if any(pd.isna(value) for value in sequence):
            return False

        # Sau reset, cumulative counter kỳ vọng không giảm và phải tăng trở lại.
        non_decreasing = all(right >= left for left, right in zip(sequence, sequence[1:]))
        recovered = sequence[-1] > sequence[0]
        return non_decreasing and recovered

    def detect_counter_resets(self, df: pd.DataFrame) -> list[CounterResetEvidence]:
        """Tìm reset candidate cho từng ``ne_id + cell_id + kpi_name``.

        Một điểm chỉ được coi là reset khi đồng thời thỏa:
        - metric nằm trong ``eligible_metrics``;
        - giá trị trước đủ lớn (``min_previous_value``);
        - giá trị hiện tại về vùng thấp (``reset_max_value``);
        - tỷ lệ giảm đủ lớn (``min_drop_ratio``);
        - các điểm sau đó cho thấy counter tích lũy tăng trở lại.
        """

        # Chỉ cumulative counter được cấu hình mới hợp lệ cho restart detection.
        eligible = set(self.config.eligible_metrics)
        if not eligible:
            return []

        work = df[df["kpi_name"].isin(eligible)].copy()
        if work.empty:
            return []

        # Chuẩn hóa timestamp và value để so sánh theo thời gian và tính tỷ lệ giảm.
        work["_timestamp"] = parse_timestamp_series(work["timestamp"])
        work["_value"] = pd.to_numeric(work["value"], errors="coerce")
        work = work.sort_values(["ne_id", "cell_id", "kpi_name", "_timestamp"])

        evidence: list[CounterResetEvidence] = []

        # Mỗi counter của mỗi cell trong NE phải được xét độc lập.
        for (ne_id, cell_id, metric_name), group in work.groupby(
            ["ne_id", "cell_id", "kpi_name"],
            sort=False,
        ):
            timestamps = group["_timestamp"].tolist()
            values = group["_value"].tolist()

            # Bắt đầu từ index=1 vì cần so current với previous.
            for index in range(1, len(values)):
                previous = values[index - 1]
                current = values[index]

                # Không thể kết luận reset nếu một trong hai điểm không có số hợp lệ.
                if pd.isna(previous) or pd.isna(current):
                    continue

                previous = float(previous)
                current = float(current)

                # Tránh hiểu nhầm giảm nhỏ như 3 -> 0 là counter reset đáng tin cậy.
                if previous < self.config.min_previous_value:
                    continue

                # Sau reset, counter phải rơi về vùng giá trị thấp được cấu hình.
                if current < 0 or current > self.config.reset_max_value:
                    continue

                # drop_ratio = phần trăm giảm so với giá trị trước reset.
                # Ví dụ 1000 -> 50 => drop_ratio = 0.95 (giảm 95%).
                drop_ratio = (previous - current) / max(abs(previous), 1e-12)
                if drop_ratio < self.config.min_drop_ratio:
                    continue

                # Candidate chỉ được giữ nếu counter tăng trở lại sau reset.
                if not self._confirm_candidate(values, index):
                    continue

                evidence.append(
                    CounterResetEvidence(
                        ne_id=str(ne_id),
                        cell_id=str(cell_id),
                        metric_name=str(metric_name),
                        timestamp=timestamps[index],
                        previous_value=previous,
                        current_value=current,
                        drop_ratio=drop_ratio,
                    )
                )

        return evidence

    def correlate_restarts(
        self,
        evidence: list[CounterResetEvidence],
    ) -> list[RestartEvent]:
        """Gom các counter reset để suy ra restart ở cấp NE.

        Một counter reset đơn lẻ chưa đủ để kết luận NE restart. Các evidence trên
        cùng NE được gom trong ``concurrent_window_minutes``; chỉ khi số metric khác
        nhau đạt ``min_concurrent_counters`` mới tạo ``RestartEvent``.
        """

        if not evidence:
            return []

        window = pd.Timedelta(minutes=self.config.concurrent_window_minutes)
        events: list[RestartEvent] = []

        # Gom evidence theo NE trước khi xét tính đồng thời.
        by_ne: dict[str, list[CounterResetEvidence]] = {}
        for item in evidence:
            by_ne.setdefault(item.ne_id, []).append(item)

        for ne_id, items in by_ne.items():
            ordered = sorted(items, key=lambda item: item.timestamp)
            index = 0

            while index < len(ordered):
                start = ordered[index].timestamp
                cluster: list[CounterResetEvidence] = []
                cursor = index

                # Gom tất cả reset nằm trong cửa sổ thời gian kể từ evidence đầu tiên.
                while cursor < len(ordered) and ordered[cursor].timestamp - start <= window:
                    cluster.append(ordered[cursor])
                    cursor += 1

                # Chỉ đếm số metric khác nhau, tránh một metric lặp lại làm tăng evidence.
                metrics = tuple(sorted({item.metric_name for item in cluster}))

                if len(metrics) >= self.config.min_concurrent_counters:
                    events.append(
                        RestartEvent(
                            ne_id=ne_id,
                            timestamp=min(item.timestamp for item in cluster),
                            metrics=metrics,
                        )
                    )
                    # Cluster này đã được dùng để tạo một restart event.
                    index = cursor
                else:
                    # Chưa đủ counter đồng thời: dịch một evidence và thử cluster tiếp theo.
                    index += 1

        return events

    def apply(self, df: pd.DataFrame) -> FilterOutcome:
        """Áp dụng restart filter và trả về dữ liệu giữ lại + dữ liệu bị exclude.

        ``cleaned_df``: các record không nằm trong restart window.
        ``excluded_df``: các record của NE từ thời điểm restart đến hết grace period,
        kèm ``filter_stage``, ``filter_reason`` và ``detail`` để audit.
        """

        require_columns(df, ("timestamp", "ne_id", "cell_id", "kpi_name", "value"))

        # Không có cumulative counter được cấu hình -> tự bỏ qua filter.
        if not self.config.eligible_metrics:
            return FilterOutcome(
                cleaned_df=df.copy(),
                excluded_df=pd.DataFrame(
                    columns=[*df.columns.tolist(), "filter_stage", "filter_reason", "detail"]
                ),
                summary={
                    "status": "SKIPPED_NO_ELIGIBLE_COUNTERS",
                    "excluded": 0,
                    "counter_resets": 0,
                    "restart_events": 0,
                },
            )

        # Bước 1: tìm reset của từng counter.
        evidence = self.detect_counter_resets(df)

        # Bước 2: tương quan nhiều counter reset để suy ra NE restart.
        restart_events = self.correlate_restarts(evidence)

        if not restart_events:
            return FilterOutcome(
                cleaned_df=df.copy(),
                excluded_df=pd.DataFrame(
                    columns=[*df.columns.tolist(), "filter_stage", "filter_reason", "detail"]
                ),
                summary={
                    "status": "ENABLED_NO_RESTART",
                    "excluded": 0,
                    "counter_resets": len(evidence),
                    "restart_events": 0,
                },
            )

        timestamps = parse_timestamp_series(df["timestamp"])

        # mask=True nghĩa là record sẽ bị chuyển sang excluded_df.
        mask = pd.Series(False, index=df.index)
        reasons = pd.Series("", index=df.index, dtype="object")
        details = pd.Series("", index=df.index, dtype="object")

        # Khoảng grace sau restart để tránh đưa giai đoạn NE chưa ổn định vào baseline.
        grace = pd.Timedelta(minutes=self.config.post_restart_grace_minutes)

        for event in restart_events:
            # Chỉ exclude đúng NE và đúng khoảng [restart_time, restart_time + grace].
            current = (
                (df["ne_id"].astype(str) == event.ne_id)
                & (timestamps >= event.timestamp)
                & (timestamps <= event.timestamp + grace)
            )

            # Chỉ ghi reason/detail cho các dòng chưa bị một restart event trước đánh dấu.
            new_rows = current & ~mask
            reasons.loc[new_rows] = "NE_RESTART_DETECTED"
            details.loc[new_rows] = (
                f"restart_time={event.timestamp.isoformat()}; "
                f"evidence_metrics={'|'.join(event.metrics)}; "
                f"grace_minutes={self.config.post_restart_grace_minutes}"
            )
            mask |= current

        # Tách DataFrame thành dữ liệu được giữ lại và dữ liệu bị loại.
        cleaned, excluded = split_by_mask(
            df,
            mask,
            stage="RESTART",
            reasons=reasons,
            details=details,
        )

        return FilterOutcome(
            cleaned_df=cleaned,
            excluded_df=excluded,
            summary={
                "status": "ENABLED",
                "excluded": int(mask.sum()),
                "counter_resets": len(evidence),
                "restart_events": len(restart_events),
            },
        )
