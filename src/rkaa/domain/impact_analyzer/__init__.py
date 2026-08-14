"""Giao diện công khai của impact_analyzer cho FR-301."""

from rkaa.domain.impact_analyzer.models import ImpactAnalysisResult, ImpactTrendAssessment
from rkaa.domain.impact_analyzer.service import ImpactAnalyzerService

__all__ = ["ImpactAnalysisResult", "ImpactAnalyzerService", "ImpactTrendAssessment"]
