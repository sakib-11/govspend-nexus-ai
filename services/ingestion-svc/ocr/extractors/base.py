"""Base extractor interface."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from ...models.extraction import ExtractionResult

class BaseExtractor(ABC):
    """Base class for all extractors."""
    
    @abstractmethod
    async def extract(
        self,
        ocr_result: Dict[str, Any],
        upload_id: str
    ) -> ExtractionResult:
        """Extract structured data from OCR result."""
        pass
