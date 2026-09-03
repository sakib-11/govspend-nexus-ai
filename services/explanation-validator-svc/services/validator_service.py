from typing import Dict, Any, List, Optional
import time
import json
from datetime import datetime
import asyncpg
from models.validation import (
    ExplanationValidationResult, ValidationRequest, ValidationStatus,
    GroundingCheck, CitationValidation
)
from services.schema_validator import SchemaValidator
from services.citation_validator import CitationValidator
from services.grounding_service import GroundingService
from services.masking_service import MaskingService
from services.rephraser_service import RephraserService
from config import ValidatorConfig
import logging

logger = logging.getLogger(__name__)

class ValidatorService:
    """Main validator service orchestrator"""
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        schema_validator: SchemaValidator,
        citation_validator: CitationValidator,
        grounding_service: GroundingService,
        masking_service: MaskingService,
        rephraser_service: RephraserService,
        config: ValidatorConfig
    ):
        self.db_pool = db_pool
        self.schema_validator = schema_validator
        self.citation_validator = citation_validator
        self.grounding_service = grounding_service
        self.masking_service = masking_service
        self.rephraser_service = rephraser_service
        self.config = config
    
    async def validate(
        self,
        request: ValidationRequest
    ) -> ExplanationValidationResult:
        """Validate an explanation"""
        
        start_time = time.time()
        
        # Initialize result
        result = ExplanationValidationResult(
            explanation_id=request.explanation_id,
            case_id=request.case_id,
            status=ValidationStatus.PENDING
        )
        
        try:
            # 1. Schema Validation
            schema_result = await self.schema_validator.validate_schema(
                request.content
            )
            result.schema_valid = schema_result.get('is_valid', False)
            
            if not result.schema_valid:
                result.errors.extend(schema_result.get('errors', []))
                result.status = ValidationStatus.FAILED
                return result
            
            # 2. Extract explanations
            explanations = request.content.get('explanations', [])
            
            # 3. Validate Citations
            citation_validations = await self.citation_validator.validate_citations(
                explanations,
                request.evidence_bundle,
                request.retrieved_policies
            )
            result.citation_validations = citation_validations
            
            # Check citation validity
            invalid_citations = [c for c in citation_validations if not c.is_valid]
            result.citations_valid = len(invalid_citations) == 0
            
            if not result.citations_valid and self.config.strict_citation_check:
                result.errors.append(f"Found {len(invalid_citations)} invalid citations")
            
            # 4. Check Grounding
            grounding_checks = await self.grounding_service.check_grounding(
                request.content,
                request.evidence_bundle,
                request.retrieved_policies
            )
            result.grounding_checks = grounding_checks
            
            # Calculate grounding score
            grounding_score = self.grounding_service.calculate_grounding_score(
                grounding_checks
            )
            result.grounding_score = grounding_score
            
            # Check 100% grounding requirement
            ungrounded = self.grounding_service.get_ungrounded_claims(grounding_checks)
            result.evidence_valid = len([g for g in ungrounded if g.claim_type == 'evidence']) == 0
            result.policy_valid = len([g for g in ungrounded if g.claim_type == 'policy']) == 0
            
            # 5. Determine validation status
            if grounding_score >= self.config.min_grounding_score:
                result.status = ValidationStatus.PASSED
            elif grounding_score >= 0.5:
                result.status = ValidationStatus.PARTIAL
            else:
                result.status = ValidationStatus.FAILED
            
            # 6. Handle ungrounded claims
            if result.status != ValidationStatus.PASSED:
                # Build issues
                for check in ungrounded:
                    issue = f"Ungrounded {check.claim_type}: {check.claim_value}"
                    result.errors.append(issue)
                
                # Mask ungrounded claims if requested
                if request.mask_ungrounded and self.config.mask_ungrounded_claims:
                    # Original content
                    result.original_content = json.dumps(request.content)
                    
                    # Mask ungrounded
                    masked = await self.masking_service.mask_ungrounded_claims(
                        request.content,
                        [c.model_dump() for c in grounding_checks]
                    )
                    result.masked_content = json.dumps(masked)
                    
                    # Rephrase if enabled
                    if request.rephrase_ungrounded and self.config.rephrase_ungrounded:
                        rephrased = await self.rephraser_service.rephrase_ungrounded_claims(
                            masked,
                            [c.model_dump() for c in ungrounded]
                        )
                        result.rephrased_content = json.dumps(rephrased)
                
                # Reject if 100% grounding required
                if self.config.require_100_percent_grounding:
                    result.status = ValidationStatus.UNGROUNDED
                    result.errors.append("100% grounding required but not achieved")
            
            # 7. Additional validations
            # Validate detector names
            valid_detectors = self._validate_detector_names(explanations)
            result.detector_names_valid = valid_detectors
            
            # 8. Calculate citation coverage
            total_citations = len(citation_validations)
            valid_citations = sum(1 for c in citation_validations if c.is_valid)
            result.citation_coverage = (
                valid_citations / total_citations if total_citations > 0 else 0
            )
            
            # 9. Store validation result
            await self._store_validation(result, request)
            
            # 10. Calculate validation time
            result.validation_time_ms = (time.time() - start_time) * 1000
            
            return result
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            result.status = ValidationStatus.FAILED
            result.errors.append(f"Validation error: {str(e)}")
            return result
    
    def _validate_detector_names(self, explanations: List[Dict[str, Any]]) -> bool:
        """Validate detector names"""
        
        valid_detectors = {
            'price_deviation', 'duplicate_fuzzy', 'vendor_graph_risk',
            'timing_anomaly', 'contract_splitting', 'approval_velocity'
        }
        
        for exp in explanations:
            detector = exp.get('detector_name', '')
            if detector and detector not in valid_detectors:
                logger.warning(f"Unknown detector: {detector}")
                if self.config.validate_detector_names:
                    return False
        
        return True
    
    async def _store_validation(
        self,
        result: ExplanationValidationResult,
        request: ValidationRequest
    ):
        """Store validation result in database"""
        
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO explanation_validations (
                    validation_id,
                    explanation_id,
                    case_id,
                    status,
                    grounding_score,
                    citation_coverage,
                    schema_valid,
                    citations_valid,
                    evidence_valid,
                    policy_valid,
                    detector_names_valid,
                    critical_issues,
                    errors,
                    warnings,
                    original_content,
                    masked_content,
                    rephrased_content,
                    validated_at,
                    validation_time_ms
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                    $11, $12, $13, $14, $15, $16, $17, $18, $19
                )
            """,
                result.validation_id,
                result.explanation_id,
                result.case_id,
                result.status.value,
                result.grounding_score,
                result.citation_coverage,
                result.schema_valid,
                result.citations_valid,
                result.evidence_valid,
                result.policy_valid,
                result.detector_names_valid,
                json.dumps(result.critical_issues),
                json.dumps(result.errors),
                json.dumps(result.warnings),
                result.original_content,
                result.masked_content,
                result.rephrased_content,
                result.validated_at,
                result.validation_time_ms
            )
    
    async def get_validation_result(
        self,
        validation_id: str
    ) -> Optional[ExplanationValidationResult]:
        """Get validation result by ID"""
        
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT * FROM explanation_validations
                WHERE validation_id = $1
            """, validation_id)
            
            if not row:
                return None
            
            return ExplanationValidationResult(
                validation_id=row['validation_id'],
                explanation_id=row['explanation_id'],
                case_id=row['case_id'],
                status=ValidationStatus(row['status']),
                grounding_score=row['grounding_score'],
                citation_coverage=row['citation_coverage'],
                schema_valid=row['schema_valid'],
                citations_valid=row['citations_valid'],
                evidence_valid=row['evidence_valid'],
                policy_valid=row['policy_valid'],
                detector_names_valid=row['detector_names_valid'],
                critical_issues=row['critical_issues'] or [],
                errors=row['errors'] or [],
                warnings=row['warnings'] or [],
                original_content=row['original_content'],
                masked_content=row['masked_content'],
                rephrased_content=row['rephrased_content'],
                validated_at=row['validated_at'],
                validation_time_ms=row['validation_time_ms'],
                grounding_checks=[],
                citation_validations=[]
            )