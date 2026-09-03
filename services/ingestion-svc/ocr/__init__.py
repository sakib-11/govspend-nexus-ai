"""OCR Service Module."""

from .core import OCRService, OCRResult, OCREngine
from .engines.tesseract import TesseractEngine
from .engines.aws_textract import AWSTextractEngine

__all__ = [
    "OCRService",
    "OCRResult",
    "OCREngine",
    "TesseractEngine",
    "AWSTextractEngine",
]

