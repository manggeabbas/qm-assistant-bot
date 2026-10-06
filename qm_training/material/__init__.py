"""Material reader package: UPLOAD -> VALIDATE -> EXTRACT -> NORMALIZE."""

from qm_training.material.base import MaterialBlock, MaterialDocument
from qm_training.material.readers import SUPPORTED_EXTENSIONS, read_material

__all__ = ["MaterialBlock", "MaterialDocument", "read_material", "SUPPORTED_EXTENSIONS"]
