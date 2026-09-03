"""Bundle validation — structural and integrity checks."""

from typing import List, Optional, Tuple
from ..models.evidence_bundle import (
    EvidenceBundle,
    BundleStatus,
    EvidenceItem,
    EvidenceSource,
    DetectorEvidence,
)


class BundleValidator:
    """Validates evidence bundles for structural correctness and integrity."""

    MAX_EVIDENCE_ITEMS = 10_000
    MAX_DETECTOR_EVIDENCES = 20
    REQUIRED_FIELDS = ("bundle_id", "transaction_id", "status")

    @staticmethod
    def validate_structure(bundle: EvidenceBundle) -> Tuple[bool, List[str]]:
        """Check structural constraints — returns (is_valid, errors)."""
        errors: List[str] = []

        # Core fields
        if not bundle.bundle_id:
            errors.append("Missing bundle_id")
        if not bundle.transaction_id:
            errors.append("Missing transaction_id")

        # Status must be a valid enum value
        try:
            BundleStatus(bundle.status)
        except ValueError:
            errors.append(f"Invalid status: {bundle.status}")

        # Evidence item count sanity
        total_items = bundle.get_evidence_count()
        if total_items > BundleValidator.MAX_EVIDENCE_ITEMS:
            errors.append(
                f"Evidence count {total_items} exceeds max {BundleValidator.MAX_EVIDENCE_ITEMS}"
            )

        # Detector evidence count
        if len(bundle.detector_evidences) > BundleValidator.MAX_DETECTOR_EVIDENCES:
            errors.append(
                f"Detector count {len(bundle.detector_evidences)} exceeds max "
                f"{BundleValidator.MAX_DETECTOR_EVIDENCES}"
            )

        # Validate individual evidence items
        for item in bundle.get_all_evidence_items():
            item_ok, item_errs = BundleValidator.validate_evidence_item(item)
            if not item_ok:
                errors.extend(item_errs)

        return (len(errors) == 0, errors)

    @staticmethod
    def validate_evidence_item(item: EvidenceItem) -> Tuple[bool, List[str]]:
        """Validate a single evidence item."""
        errors: List[str] = []

        if not item.evidence_id:
            errors.append(f"EvidenceItem missing evidence_id (source={item.source})")
        if not item.source_type:
            errors.append(f"EvidenceItem missing source_type (id={item.evidence_id})")
        if item.confidence is not None and not (0.0 <= item.confidence <= 1.0):
            errors.append(
                f"EvidenceItem confidence {item.confidence} out of range (id={item.evidence_id})"
            )
        if not (0.0 <= item.relevance_score <= 1.0):
            errors.append(
                f"EvidenceItem relevance_score {item.relevance_score} out of range "
                f"(id={item.evidence_id})"
            )

        return (len(errors) == 0, errors)

    @staticmethod
    def validate_detector_evidence(det: DetectorEvidence) -> Tuple[bool, List[str]]:
        """Validate a detector evidence block."""
        errors: List[str] = []

        if not det.detector_type:
            errors.append("DetectorEvidence missing detector_type")
        if not (0.0 <= det.signal_value <= 1.0):
            errors.append(
                f"signal_value {det.signal_value} out of range for {det.detector_type}"
            )
        if not (0.0 <= det.confidence <= 1.0):
            errors.append(
                f"confidence {det.confidence} out of range for {det.detector_type}"
            )

        return (len(errors) == 0, errors)

    @staticmethod
    def validate_checksum(bundle: EvidenceBundle) -> bool:
        """Verify stored checksum matches recomputed checksum."""
        if not bundle.storage_checksum:
            return True  # No checksum stored — nothing to verify
        return bundle.compute_checksum() == bundle.storage_checksum

    @staticmethod
    def full_validation(bundle: EvidenceBundle) -> Tuple[bool, List[str]]:
        """Run every validation check.  Returns (all_passed, combined_errors)."""
        all_errors: List[str] = []

        struct_ok, struct_errs = BundleValidator.validate_structure(bundle)
        all_errors.extend(struct_errs)

        for det in bundle.detector_evidences:
            det_ok, det_errs = BundleValidator.validate_detector_evidence(det)
            all_errors.extend(det_errs)

        if bundle.storage_checksum:
            if not BundleValidator.validate_checksum(bundle):
                all_errors.append("Checksum mismatch — bundle may be corrupted")

        return (len(all_errors) == 0, all_errors)
