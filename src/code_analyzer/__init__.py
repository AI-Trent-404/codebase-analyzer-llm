"""LLM-powered codebase analyzer that emits structured, machine-readable JSON."""

__version__ = "1.0.0"

from .config import Settings
from .models import CodebaseAnalysis
from .pipeline import AnalysisPipeline

__all__ = ["Settings", "CodebaseAnalysis", "AnalysisPipeline", "__version__"]
