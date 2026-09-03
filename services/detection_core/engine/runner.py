"""Detector Runner - Executes detectors against transactions."""

import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import uuid

from ..detectors.registry import DetectorRegistry
from ..models.engine import DetectorExecution, DetectorStatus, TransactionContext
from ..models.signals import Signal, Evidence, DetectionType
from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class DetectorRunner:
    """Execute detectors against transactions"""

    def __init__(self, registry: Optional[DetectorRegistry] = None):
        self.registry = registry or DetectorRegistry()
        self.timeout_seconds = settings.DETECTOR_TIMEOUT_SECONDS
        self.max_retries = settings.MAX_RETRIES
        self.retry_delay = settings.RETRY_DELAY_SECONDS

    async def run_all_detectors(
        self,
        transaction_context: TransactionContext,
        parallel: bool = True
    ) -> Tuple[List[Signal], List[DetectorExecution]]:
        """
        Run all registered detectors on a transaction
        """
        detector_ids = self.registry.get_all_detectors()
        signals = []
        executions = []

        if parallel:
            # Run detectors in parallel
            tasks = []
            for detector_id in detector_ids:
                task = self.run_single_detector(
                    detector_id,
                    transaction_context,
                    self.max_retries
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for detector_id, result in zip(detector_ids, results):
                if isinstance(result, Exception):
                    execution = DetectorExecution(
                        detector_id=detector_id,
                        detector_name=detector_id,
                        status=DetectorStatus.FAILED,
                        error=str(result)
                    )
                    executions.append(execution)
                    logger.error(f"Detector {detector_id} failed: {result}")
                else:
                    signal, execution = result
                    if signal:
                        signals.append(signal)
                    executions.append(execution)
        else:
            # Run detectors sequentially
            for detector_id in detector_ids:
                try:
                    signal, execution = await self.run_single_detector(
                        detector_id,
                        transaction_context,
                        self.max_retries
                    )
                    if signal:
                        signals.append(signal)
                    executions.append(execution)
                except Exception as e:
                    execution = DetectorExecution(
                        detector_id=detector_id,
                        detector_name=detector_id,
                        status=DetectorStatus.FAILED,
                        error=str(e)
                    )
                    executions.append(execution)
                    logger.error(f"Detector {detector_id} failed: {e}")

        return signals, executions

    async def run_single_detector(
        self,
        detector_id: str,
        transaction_context: TransactionContext,
        max_retries: int = 3
    ) -> Tuple[Optional[Signal], DetectorExecution]:
        """
        Run a single detector with retries
        """
        execution = DetectorExecution(
            detector_id=detector_id,
            detector_name=detector_id,
            status=DetectorStatus.PENDING,
            start_time=datetime.utcnow()
        )

        # Get detector instance
        detector = self.registry.get_detector(detector_id)
        if not detector:
            execution.status = DetectorStatus.FAILED
            execution.error = f"Detector {detector_id} not registered"
            execution.end_time = datetime.utcnow()
            return None, execution

        # Get detector weight
        weight = self.registry.get_weight(detector_id)

        # Run with retries
        retry_count = 0
        last_error = None

        while retry_count <= max_retries:
            try:
                execution.start_time = datetime.utcnow()
                execution.retry_count = retry_count

                # Run detector with timeout
                start_time = time.time()
                result = await asyncio.wait_for(
                    detector.detect(transaction_context.canonical_transaction),
                    timeout=self.timeout_seconds
                )
                duration_ms = (time.time() - start_time) * 1000

                # Create signal from result
                signal = self._create_signal(
                    detector_id,
                    transaction_context,
                    result,
                    weight,
                    duration_ms
                )

                execution.status = DetectorStatus.COMPLETED
                execution.result = result
                execution.duration_ms = duration_ms
                execution.end_time = datetime.utcnow()

                logger.info(
                    f"Detector {detector_id} completed in {duration_ms:.0f}ms "
                    f"signal={result.get('signal_value', 0):.3f}"
                )

                return signal, execution

            except asyncio.TimeoutError:
                last_error = f"Detector {detector_id} timed out after {self.timeout_seconds}s"
                logger.warning(f"{last_error}, retry {retry_count+1}/{max_retries}")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Detector {detector_id} failed: {e}, retry {retry_count+1}/{max_retries}")

            retry_count += 1
            if retry_count <= max_retries:
                await asyncio.sleep(self.retry_delay)

        # All retries exhausted
        execution.status = DetectorStatus.FAILED
        execution.error = last_error or f"Max retries ({max_retries}) exceeded"
        execution.end_time = datetime.utcnow()

        return None, execution

    def _create_signal(
        self,
        detector_id: str,
        context: TransactionContext,
        result: Dict[str, Any],
        weight: float,
        duration_ms: float
    ) -> Signal:
        """Create signal from detector result"""
        signal_id = str(uuid.uuid4())

        # Extract signal value and confidence
        signal_value = result.get('signal_value', 0.0)
        confidence = result.get('confidence', 0.0)
        raw_value = result.get('raw_deviation', signal_value)

        # Extract evidence
        evidence = self._extract_evidence(signal_id, detector_id, context, result)

        # Determine detection type
        detection_type = self._get_detection_type(detector_id)

        return Signal(
            signal_id=signal_id,
            transaction_id=context.transaction_id,
            detector_id=detector_id,
            detection_type=detection_type,
            value=signal_value,
            confidence=confidence,
            raw_value=raw_value,
            weight=weight,
            department_id=context.department_id,
            vendor_id=context.vendor_id,
            evidence_ids=[e.evidence_id for e in evidence],
            evidence=evidence,
            metadata=result.get('metadata', {}),
            execution_time_ms=duration_ms
        )

    def _extract_evidence(
        self,
        signal_id: str,
        detector_id: str,
        context: TransactionContext,
        result: Dict[str, Any]
    ) -> List[Evidence]:
        """Extract evidence from detector result"""
        evidence_list = []

        # Get evidence strings from result
        evidence_texts = result.get('evidence', [])

        for i, text in enumerate(evidence_texts):
            evidence_id = f"evi_{signal_id}_{i}"

            evidence = Evidence(
                evidence_id=evidence_id,
                signal_id=signal_id,
                evidence_type="detector_output",
                description=text[:500],  # Truncate
                data={"text": text},
                source_type="detector",
                source_id=detector_id
            )
            evidence_list.append(evidence)

        # Add transaction context evidence
        if context.amount:
            evidence = Evidence(
                evidence_id=f"evi_{signal_id}_amount",
                signal_id=signal_id,
                evidence_type="transaction_context",
                description=f"Transaction amount: ${context.amount:,.2f}",
                data={"amount": context.amount},
                source_type="transaction",
                source_id=context.transaction_id
            )
            evidence_list.append(evidence)

        return evidence_list

    def _get_detection_type(self, detector_id: str) -> DetectionType:
        """Map detector ID to detection type"""
        mapping = {
            'price_deviation': DetectionType.PRICE_DEVIATION,
            'duplicate_fuzzy': DetectionType.DUPLICATE,
            'vendor_graph_risk': DetectionType.VENDOR_RISK,
            'timing_anomaly': DetectionType.TIMING_ANOMALY,
            'contract_splitting': DetectionType.CONTRACT_SPLITTING,
            'approval_velocity': DetectionType.APPROVAL_VELOCITY
        }
        return mapping.get(detector_id, DetectionType.PRICE_DEVIATION)