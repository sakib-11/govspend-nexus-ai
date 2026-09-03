"""Invoice data extractor combining OCR extraction and invoice mapping."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional
import logging
import re

from .base import BaseExtractor
from .field_mapper import FieldMapper
from .confidence_scorer import ConfidenceScorer
from .heuristic_rules import HeuristicRulesEngine

from ...models.extraction import (
    ExtractedField,
    ExtractionResult,
)

from ...models.invoice import InvoiceData, LineItem

logger = logging.getLogger(__name__)


class InvoiceDataExtractor(BaseExtractor):
    """Extract structured invoice data from OCR results."""

    def __init__(self) -> None:
        """Initialize extraction components."""
        super().__init__()

        self.rules_engine = HeuristicRulesEngine()
        self.field_mapper = FieldMapper()
        self.confidence_scorer = ConfidenceScorer()

    async def extract(
        self,
        ocr_result: Dict[str, Any],
        upload_id: str,
    ) -> ExtractionResult:
        """
        Extract structured invoice fields from OCR results.

        Args:
            ocr_result: OCR result containing raw_text and confidence.
            upload_id: Unique upload identifier.

        Returns:
            ExtractionResult containing extracted fields and confidence scores.
        """
        start_time = datetime.now()

        try:
            raw_text = ocr_result.get("raw_text", "") or ""
            lines = raw_text.splitlines()

            # Map OCR text to invoice fields.
            extracted_fields = self.field_mapper.map_fields(
                text=raw_text,
                lines=lines,
                ocr_results=ocr_result,
            )

            if not extracted_fields:
                extracted_fields = {}

            # Calculate confidence for every extracted field.
            ocr_confidence = self._safe_float(
                ocr_result.get("confidence", 0.0)
            )

            for name, field in extracted_fields.items():
                try:
                    field.confidence = (
                        self.confidence_scorer.calculate_field_confidence(
                            field,
                            context={
                                "ocr_confidence": ocr_confidence,
                            },
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to calculate confidence for field '%s': %s",
                        name,
                        exc,
                    )

                    if getattr(field, "confidence", None) is None:
                        field.confidence = 0.0

            confidence_scores = {
                name: float(getattr(field, "confidence", 0.0) or 0.0)
                for name, field in extracted_fields.items()
            }

            overall_confidence = (
                self.confidence_scorer.calculate_overall_confidence(
                    extracted_fields
                )
                if extracted_fields
                else 0.0
            )

            extraction_time_ms = (
                datetime.now() - start_time
            ).total_seconds() * 1000

            return ExtractionResult(
                upload_id=upload_id,
                extracted_fields=extracted_fields,
                confidence_scores=confidence_scores,
                overall_confidence=float(overall_confidence),
                extraction_time_ms=extraction_time_ms,
                warnings=self._generate_warnings(extracted_fields),
            )

        except Exception as exc:
            logger.exception(
                "Invoice extraction failed for upload '%s'",
                upload_id,
            )

            extraction_time_ms = (
                datetime.now() - start_time
            ).total_seconds() * 1000

            return ExtractionResult(
                upload_id=upload_id,
                extracted_fields={},
                confidence_scores={},
                overall_confidence=0.0,
                extraction_time_ms=extraction_time_ms,
                warnings=[f"Invoice extraction failed: {str(exc)}"],
            )

    def extract_from_fields(
        self,
        fields: Dict[str, Any],
    ) -> Optional[InvoiceData]:
        """
        Convert extracted OCR fields into an InvoiceData object.

        Args:
            fields: Dictionary containing mapped invoice fields.

        Returns:
            InvoiceData object or None when extraction fails.
        """
        if not fields:
            return None

        try:
            invoice = InvoiceData()

            # Basic invoice information.
            self._set_if_present(
                invoice,
                "invoice_number",
                fields.get("invoice_number"),
            )

            self._set_if_present(
                invoice,
                "purchase_order",
                fields.get("purchase_order"),
            )

            self._set_if_present(
                invoice,
                "vendor_name",
                fields.get("vendor_name"),
            )

            self._set_if_present(
                invoice,
                "vendor_tax_id",
                fields.get("vendor_tax_id"),
            )

            self._set_if_present(
                invoice,
                "buyer_name",
                fields.get("buyer_name"),
            )

            # Dates.
            invoice_date = self._parse_date(
                fields.get("invoice_date") or fields.get("date")
            )

            due_date = self._parse_date(
                fields.get("due_date")
            )

            self._set_if_present(
                invoice,
                "invoice_date",
                invoice_date,
            )

            self._set_if_present(
                invoice,
                "due_date",
                due_date,
            )

            # Total amount.
            total_amount = self._parse_amount(
                fields.get("total_amount")
            )

            self._set_if_present(
                invoice,
                "total_amount",
                total_amount,
            )

            # Line items.
            line_items = self._parse_line_items(
                fields.get("line_items")
            )

            if line_items is not None:
                self._set_if_present(
                    invoice,
                    "line_items",
                    line_items,
                )

            return invoice

        except Exception as exc:
            logger.exception(
                "Failed to create InvoiceData: %s",
                exc,
            )
            return None

    def _parse_line_items(
        self,
        items: Any,
    ) -> Optional[List[LineItem]]:
        """
        Convert raw line item dictionaries into LineItem objects.
        """
        if not items:
            return None

        if not isinstance(items, list):
            logger.warning("Invalid line_items format: expected list")
            return None

        parsed_items: List[LineItem] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            try:
                description = str(
                    item.get("description", "")
                ).strip()

                quantity = self._safe_int(
                    item.get("quantity", 1),
                    default=1,
                )

                unit_price = self._safe_float(
                    item.get("unit_price", 0.0),
                    default=0.0,
                )

                total = self._safe_float(
                    item.get("total", 0.0),
                    default=0.0,
                )

                parsed_items.append(
                    LineItem(
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        total=total,
                    )
                )

            except Exception as exc:
                logger.warning(
                    "Skipping invalid line item: %s",
                    exc,
                )

        return parsed_items or None

    @staticmethod
    def _parse_date(
        value: Any,
    ) -> Optional[date]:
        """
        Parse a date from common invoice date formats.
        """
        if value is None:
            return None

        if isinstance(value, date):
            return value

        value = str(value).strip()

        if not value:
            return None

        formats = (
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%Y/%m/%d",
            "%Y%m%d",
            "%d-%m-%Y",
            "%d.%m.%Y",
        )

        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue

        logger.warning(
            "Could not parse date value: %s",
            value,
        )

        return None

    @staticmethod
    def _parse_amount(
        value: Any,
    ) -> Optional[float]:
        """
        Parse a monetary value from OCR text.
        """
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        value = str(value).strip()

        if not value:
            return None

        # Remove currency symbols and common separators.
        cleaned = re.sub(
            r"[^\d.\-]",
            "",
            value,
        )

        if not cleaned:
            return None

        try:
            return float(cleaned)
        except ValueError:
            logger.warning(
                "Could not parse amount value: %s",
                value,
            )
            return None

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        """Safely convert a value to float."""
        try:
            if value is None:
                return default

            if isinstance(value, str):
                value = value.strip()

                if not value:
                    return default

            return float(value)

        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(
        value: Any,
        default: int = 1,
    ) -> int:
        """Safely convert a value to integer."""
        try:
            if value is None:
                return default

            if isinstance(value, str):
                value = value.strip()

                if not value:
                    return default

                # Handle values such as "2.0".
                return int(float(value))

            return int(value)

        except (TypeError, ValueError):
            return default

    @staticmethod
    def _set_if_present(
        obj: Any,
        attribute: str,
        value: Any,
    ) -> None:
        """
        Set an attribute only when the value is not None.

        This makes the extractor tolerant of different InvoiceData
        model implementations.
        """
        if value is None:
            return

        try:
            setattr(obj, attribute, value)
        except Exception as exc:
            logger.warning(
                "Could not set '%s' on %s: %s",
                attribute,
                type(obj).__name__,
                exc,
            )

    def _generate_warnings(
        self,
        extracted_fields: Dict[str, ExtractedField],
    ) -> List[str]:
        """
        Generate validation and extraction warnings.
        """
        warnings: List[str] = []

        if not extracted_fields:
            warnings.append(
                "No invoice fields were extracted."
            )
            return warnings

        # Required fields.
        required_fields = [
            "vendor_name",
            "total_amount",
            "date",
        ]

        missing_fields = []

        for field_name in required_fields:
            field = extracted_fields.get(field_name)

            if field is None:
                missing_fields.append(field_name)
                continue

            value = getattr(field, "value", None)

            if value is None or str(value).strip() == "":
                missing_fields.append(field_name)

        if missing_fields:
            warnings.append(
                "Missing required fields: "
                + ", ".join(missing_fields)
            )

        # Low confidence fields.
        for name, field in extracted_fields.items():
            confidence = self._safe_float(
                getattr(field, "confidence", 0.0),
                default=0.0,
            )

            if confidence < 0.5:
                warnings.append(
                    f"Low confidence ({confidence:.2f}) "
                    f"for field: {name}"
                )

        # Check total against line items.
        total_field = extracted_fields.get("total_amount")
        line_items_field = extracted_fields.get("line_items")

        if total_field and line_items_field:
            total = self._safe_float(
                getattr(total_field, "value", 0.0),
                default=0.0,
            )

            line_items = getattr(
                line_items_field,
                "value",
                None,
            )

            if total > 0 and isinstance(line_items, list):
                calculated_total = 0.0

                for item in line_items:
                    if isinstance(item, dict):
                        calculated_total += self._safe_float(
                            item.get("total", 0.0),
                            default=0.0,
                        )

                if calculated_total > 0:
                    difference = abs(
                        total - calculated_total
                    )

                    percentage_difference = (
                        difference / max(abs(total), 1.0)
                    )

                    if percentage_difference > 0.05:
                        warnings.append(
                            "Total amount mismatch: "
                            f"extracted {total:.2f} vs "
                            f"line items total "
                            f"{calculated_total:.2f}"
                        )

        return warnings
