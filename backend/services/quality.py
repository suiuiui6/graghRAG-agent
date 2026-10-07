"""
Quality Monitor — §5.5 of enterprise-evolution-blueprint.

Computes 4-dimension data quality metrics: extraction quality,
retrieval quality, user feedback quality, and data freshness.
Updates Prometheus gauges and generates quality reports.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from models import QualityReport
from logging_config import get_logger

logger = get_logger(__name__)

KG_DIR = Path("output/kg")
FEEDBACK_DIR = Path("output/feedback")
CONVERSATIONS_DIR = Path("output/conversations")
DOCS_STORE = Path("output/docs_store.json")


class QualityMonitor:
    """Computes data quality metrics and updates Prometheus gauges."""

    def __init__(self):
        import metrics as m
        self._m = m

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── main ────────────────────────────────────────────────────────────

    def compute(self) -> QualityReport:
        extraction = self._extraction_quality()
        retrieval = self._retrieval_quality()
        feedback = self._feedback_quality()
        freshness = self._data_freshness()

        alerts: list[dict] = []
        if extraction["grounding_rate"] < 0.5:
            alerts.append({"severity": "warning", "metric": "grounding_rate",
                          "value": extraction["grounding_rate"], "threshold": 0.5})
        if feedback["positive_ratio"] < 0.5:
            alerts.append({"severity": "critical", "metric": "positive_ratio",
                          "value": feedback["positive_ratio"], "threshold": 0.5})
        if freshness["days_since_last_ingest"] > 30:
            alerts.append({"severity": "warning", "metric": "data_freshness",
                          "value": freshness["days_since_last_ingest"], "threshold": 30})

        overall = self._compute_overall(extraction, retrieval, feedback, freshness)

        # Update Prometheus gauges
        try:
            self._m.rag_grounding_rate.set(extraction["grounding_rate"])
            self._m.rag_positive_feedback_ratio.set(feedback["positive_ratio"])
            self._m.rag_stale_entities.set(freshness["stale_entities"])
            self._m.rag_data_freshness_days.set(freshness["days_since_last_ingest"])
            self._m.rag_quality_score.set(overall)
        except Exception:  # noqa: S110, BLE001  # 指标上报为旁路，失败不影响质量报告返回
            pass

        # Publish quality alerts
        for alert in alerts:
            try:
                from services.event_bus import get_event_bus
                get_event_bus().publish("quality.alert", {
                    "alert_level": alert["severity"],
                    "metric": alert["metric"],
                    "value": alert["value"],
                    "threshold": alert["threshold"],
                    "overall_score": overall,
                })
            except Exception:  # noqa: S110, BLE001  # 事件发布为 fire-and-forget，单条告警投递失败不阻断其余告警
                pass

        report = QualityReport(
            extraction_quality=extraction,
            retrieval_quality=retrieval,
            feedback_quality=feedback,
            data_freshness=freshness,
            overall_score=overall,
            alerts=alerts,
            generated_at=self._now(),
        )

        logger.info("quality_report_generated", score=overall, alerts=len(alerts))
        return report

    # ── dimension 1: extraction quality ─────────────────────────────────

    def _extraction_quality(self) -> dict:
        total = 0
        grounded = 0
        confidence_sum = 0.0
        error_docs = 0

        for entry_dir in KG_DIR.iterdir() if KG_DIR.exists() else []:
            if not entry_dir.is_dir() or not entry_dir.name.startswith("doc_"):
                continue
            n_path = entry_dir / "nodes.json"
            if not n_path.exists():
                error_docs += 1
                continue
            try:
                nodes = json.loads(n_path.read_text(encoding="utf-8")).get("nodes", [])
                total += len(nodes)
                for n in nodes:
                    if n.get("grounding_status") == "grounded":
                        grounded += 1
                    conf = n.get("properties", {}).get("confidence", 0)
                    if isinstance(conf, (int, float)):
                        confidence_sum += conf
            except Exception:  # noqa: BLE001  # 统计聚合降级：单维失败不应让整个接口失败
                error_docs += 1

        # Backwards compatible: flat format
        if total == 0:
            flat_n = KG_DIR / "nodes.json"
            if flat_n.exists():
                try:
                    nodes = json.loads(flat_n.read_text(encoding="utf-8")).get("nodes", [])
                    total = len(nodes)
                    for n in nodes:
                        if n.get("grounding_status") == "grounded":
                            grounded += 1
                except Exception:  # noqa: S110, BLE001  # 统计聚合降级：单维读取失败不应让整个接口失败
                    pass

        return {
            "grounding_rate": round(grounded / total, 4) if total > 0 else 0.0,
            "confidence_avg": round(confidence_sum / max(total, 1), 4),
            "extraction_error_rate": round(error_docs / max(total, 1), 4),
            "total_entities": total,
            "grounded_entities": grounded,
        }

    # ── dimension 2: retrieval quality ──────────────────────────────────

    def _retrieval_quality(self) -> dict:
        try:
            samples = list(self._m.rag_retrieval_candidates.collect())
            path_cover = 0
            for s in samples:
                for sample in s.samples:
                    if sample.value > 0:
                        path_cover += 1
        except Exception:  # noqa: BLE001  # 统计聚合降级：单维失败不应让整个接口失败
            path_cover = 0

        try:
            zero_result = self._m.rag_zero_result_queries._value.get()
        except Exception:  # noqa: BLE001  # 统计聚合降级：单维失败不应让整个接口失败
            zero_result = 0

        return {
            "path_covers_avg": path_cover,
            "zero_result_total": zero_result,
        }

    # ── dimension 3: user feedback quality ──────────────────────────────

    def _feedback_quality(self) -> dict:
        total = 0
        positive = 0
        negative_queries: list[str] = []
        for f in FEEDBACK_DIR.glob("*.json") if FEEDBACK_DIR.exists() else []:
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
                total += 1
                if rec.get("rating") == "positive":
                    positive += 1
                else:
                    q = rec.get("query_text", "")[:80]
                    if q:
                        negative_queries.append(q)
            except Exception:  # noqa: S110, BLE001  # 统计聚合降级：单维读取失败不应让整个接口失败
                pass
        return {
            "total": total,
            "positive": positive,
            "negative": total - positive,
            "positive_ratio": round(positive / total, 4) if total > 0 else 0.0,
            "negative_clusters": list(set(negative_queries))[:10],
        }

    # ── dimension 4: data freshness ─────────────────────────────────────

    def _data_freshness(self) -> dict:
        # Days since last ingest
        days_since = 999
        if DOCS_STORE.exists():
            try:
                docs = json.loads(DOCS_STORE.read_text(encoding="utf-8"))
                if docs:
                    latest = max(
                        (d.get("indexed_at", "2000-01-01T00:00:00") for d in docs),
                        default="2000-01-01T00:00:00")
                    latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
                    days_since = (datetime.now(timezone.utc) - latest_dt).days
            except Exception:  # noqa: S110, BLE001  # 统计聚合降级：单维读取失败不应让整个接口失败
                pass

        # Count stale entities (no hits in 30 days — simple proxy: total entities)
        stale = 0
        today = datetime.now(timezone.utc)
        for entry_dir in KG_DIR.iterdir() if KG_DIR.exists() else []:
            if not entry_dir.is_dir() or not entry_dir.name.startswith("doc_"):
                continue
            n_path = entry_dir / "nodes.json"
            if not n_path.exists():
                continue
            try:
                mtime = datetime.fromtimestamp(n_path.stat().st_mtime, tz=timezone.utc)
                if (today - mtime).days > 30:
                    stale += len(json.loads(n_path.read_text(encoding="utf-8")).get("nodes", []))
            except Exception:  # noqa: S110, BLE001  # 统计聚合降级：单维读取失败不应让整个接口失败
                pass

        return {
            "days_since_last_ingest": days_since,
            "stale_entities": stale,
            "conversation_active_today": self._active_today(),
        }

    def _active_today(self) -> int:
        if not CONVERSATIONS_DIR.exists():
            return 0
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        count = 0
        for f in CONVERSATIONS_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                last = data.get("last_active", "")
                if last.startswith(today):
                    count += 1
            except Exception:  # noqa: S110, BLE001  # 统计聚合降级：单维读取失败不应让整个接口失败
                pass
        return count

    # ── overall score ──────────────────────────────────────────────────

    def _compute_overall(self, extraction: dict, retrieval: dict,
                         feedback: dict, freshness: dict) -> float:
        score = 0.0
        # Extraction: grounding_rate (weight 0.4)
        score += extraction.get("grounding_rate", 0) * 40
        # Retrieval: path coverage (weight 0.2)
        paths = retrieval.get("path_covers_avg", 0)
        score += min(paths / 5.0, 1.0) * 20
        # Feedback: positive ratio (weight 0.3)
        score += feedback.get("positive_ratio", 0) * 30
        # Freshness: recency (weight 0.1)
        days = freshness.get("days_since_last_ingest", 999)
        freshness_score = max(0, 1 - days / 60)  # 0 at 60+ days
        score += freshness_score * 10
        return round(score, 1)


# ── singleton ─────────────────────────────────────────────────────────────

_monitor: QualityMonitor | None = None


def get_quality_monitor() -> QualityMonitor:
    global _monitor
    if _monitor is None:
        _monitor = QualityMonitor()
    return _monitor
