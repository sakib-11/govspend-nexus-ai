from typing import List, Dict, Any, Optional, Tuple
import re
from models.validation import MaskingResult, ValidationStatus
from config import ValidatorConfig

class MaskingService:
    """Service for masking ungrounded claims"""
    
    def __init__(self, config: ValidatorConfig):
        self.config = config
        self.mask_marker = config.mask_marker
    
    async def mask_ungrounded_claims(
        self,
        explanation: Dict[str, Any],
        grounding_checks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Mask ungrounded claims in explanation"""
        
        masked_explanation = explanation.copy()
        masked_count = 0
        
        # Process each explanation point
        for idx, exp in enumerate(masked_explanation.get('explanations', [])):
            sentence = exp.get('sentence', '')
            
            # Check if this point has ungrounded claims
            point_grounding = self._get_point_grounding(
                exp,
                grounding_checks
            )
            
            if not point_grounding['is_grounded']:
                # Mask the sentence
                masked_sentence = await self._mask_sentence(
                    sentence,
                    point_grounding['ungrounded_terms']
                )
                exp['sentence'] = masked_sentence
                exp['grounding_status'] = ValidationStatus.MASKED.value
                masked_count += 1
        
        # Update metadata
        masked_explanation['masking_applied'] = True
        masked_explanation['masked_count'] = masked_count
        masked_explanation['mask_marker'] = self.mask_marker
        
        return masked_explanation
    
    def _get_point_grounding(
        self,
        explanation_point: Dict[str, Any],
        grounding_checks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check if an explanation point is grounded"""
        
        ungrounded_terms = []
        is_grounded = True
        
        # Check evidence IDs
        for evidence_id in explanation_point.get('evidence_ids', []):
            if not self._is_evidence_grounded(evidence_id, grounding_checks):
                ungrounded_terms.append(f"Evidence {evidence_id}")
                is_grounded = False
        
        # Check policy references
        for policy_ref in explanation_point.get('policy_references', []):
            if not self._is_policy_grounded(policy_ref, grounding_checks):
                ungrounded_terms.append(f"Policy {policy_ref}")
                is_grounded = False
        
        # Check citations
        for citation in explanation_point.get('citations', []):
            ref_id = citation.get('reference_id', '')
            if not self._is_citation_grounded(ref_id, grounding_checks):
                ungrounded_terms.append(f"Citation {ref_id}")
                is_grounded = False
        
        return {
            'is_grounded': is_grounded,
            'ungrounded_terms': ungrounded_terms
        }
    
    async def _mask_sentence(
        self,
        sentence: str,
        ungrounded_terms: List[str]
    ) -> str:
        """Mask ungrounded terms in a sentence"""
        
        masked_sentence = sentence
        
        for term in ungrounded_terms:
            # Mask specific patterns
            if term.startswith('Evidence'):
                # Mask evidence references
                masked_sentence = re.sub(
                    r'EV-\d+',
                    f'{self.mask_marker}',
                    masked_sentence
                )
            elif term.startswith('Policy'):
                # Mask policy references
                masked_sentence = re.sub(
                    r'GFR-\d+\.\d+',
                    f'{self.mask_marker}',
                    masked_sentence
                )
            elif term.startswith('Citation'):
                # Mask citation references
                masked_sentence = re.sub(
                    r'\[[A-Z0-9\-]+\]',
                    f'{self.mask_marker}',
                    masked_sentence
                )
        
        # If sentence still has ungrounded claims, add marker
        if any(term in masked_sentence for term in ungrounded_terms):
            masked_sentence = f"{masked_sentence} {self.mask_marker}"
        
        return masked_sentence
    
    def _is_evidence_grounded(
        self,
        evidence_id: str,
        grounding_checks: List[Dict[str, Any]]
    ) -> bool:
        """Check if evidence ID is grounded"""
        
        for check in grounding_checks:
            if (check.get('claim_type') == 'evidence' and
                evidence_id in check.get('claim_value', '')):
                return check.get('is_grounded', False)
        return False
    
    def _is_policy_grounded(
        self,
        policy_ref: str,
        grounding_checks: List[Dict[str, Any]]
    ) -> bool:
        """Check if policy reference is grounded"""
        
        for check in grounding_checks:
            if (check.get('claim_type') == 'policy' and
                policy_ref in check.get('claim_value', '')):
                return check.get('is_grounded', False)
        return False
    
    def _is_citation_grounded(
        self,
        citation_id: str,
        grounding_checks: List[Dict[str, Any]]
    ) -> bool:
        """Check if citation is grounded"""
        
        for check in grounding_checks:
            if (check.get('claim_type') in ['evidence', 'policy'] and
                check.get('source_id') == citation_id):
                return check.get('is_grounded', False)
        return False
    
    def get_masking_summary(
        self,
        original: Dict[str, Any],
        masked: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get summary of masking applied"""
        
        original_exps = original.get('explanations', [])
        masked_exps = masked.get('explanations', [])
        
        return {
            "total_explanations": len(original_exps),
            "masked_explanations": masked.get('masked_count', 0),
            "mask_marker": self.mask_marker,
            "grounding_status": ValidationStatus.MASKED.value,
            "masked_percentage": (
                masked.get('masked_count', 0) / len(original_exps) * 100
                if original_exps else 0
            )
        }