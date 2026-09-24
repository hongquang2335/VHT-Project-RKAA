"""Impact analysis application service for FR-301/FR-302."""

from rkaa.application.impact_analyzer.analyzer import ImpactAnalyzer
from rkaa.application.impact_analyzer.models import ImpactAnalysisConfig

__all__ = ["ImpactAnalysisConfig", "ImpactAnalyzer"]
