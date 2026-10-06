"""Document engine package."""

from qm_training.document.engine import build_document, generate
from qm_training.document.schema import QAPair, TrainingData

__all__ = ["TrainingData", "QAPair", "build_document", "generate"]
