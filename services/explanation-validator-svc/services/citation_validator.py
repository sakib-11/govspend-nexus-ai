from typing import List, Dict, Any, Set, Optional
from datetime import datetime
from models.validation import CitationValidation, CitationStatus

class CitationValidator:
    """Validate citations against evidence bundle and policies"""
    
    def __init__(self):
        self._evidence_cache = {}
        self._policy_cache = {}
    
    async def validate_citations(
        self,
        explanations: List[Dict[str, Any]],
        evidence_bundle: Dict[str, Any],
        retrieved_policies: List[Dict[str, Any]]
    ) -> List[CitationValidation]:
        """Validate all citations in explanations"""
        
        # Build lookup sets
        evidence_ids = self._get_evidence_ids(evidence_bundle)
        policy_ids = self._get_policy_ids(retrieved_policies)
        
        validations = []
        
        for exp in explanations:
            # Check evidence citations
            for evidence_id in exp.get('evidence_ids', []):
                validation = await self._validate_evidence_citation(
                    evidence_id,
                    evidence_ids,
                    exp
                )
                validations.append(validation)
            
            # Check policy citations
            for policy_ref in exp.get('policy_references', []):
                validation = await self._validate_policy_citation(
                    policy_ref,
                    policy_ids,
                    exp
                )
                validations.append(validation)
            
            # Check structured citations
            for citation in exp.get('citations', []):
                if citation.get('citation_type') == 'evidence':
                    validation = await self._validate_evidence_citation(
                        citation.get('reference_id', ''),
                        evidence_ids,
                        exp,
                        citation_text=citation.get('reference_text', '')
                    )
                    validations.append(validation)
                elif citation.get('citation_type') == 'policy':
                    validation = await self._validate_policy_citation(
                        citation.get('reference_id', ''),
                        policy_ids,
                        exp,
                        citation_text=citation.get('reference_text', '')
                    )
                    validations.append(validation)
        
        return validations
    
    async def _validate_evidence_citation(
        self,
        evidence_id: str,
        evidence_ids: Set[str],
        explanation: Dict[str, Any],
        citation_text: Optional[str] = None
    ) -> CitationValidation:
        """Validate an evidence citation"""
        
        exists_in_bundle = evidence_id in evidence_ids
        is_valid = exists_in_bundle
        
        status = CitationStatus.VALID if is_valid else CitationStatus.INVALID
        
        return CitationValidation(
            citation_id=f"evid-{evidence_id}",
            citation_type="evidence",
            reference_id=evidence_id,
            reference_text=citation_text or f"Evidence {evidence_id}",
            exists_in_bundle=exists_in_bundle,
            exists_in_corpus=exists_in_bundle,
            is_valid=is_valid,
            status=status,
            validation_details={
                "explanation_point": explanation.get('point_number'),
                "detector": explanation.get('detector_name'),
                "validated_at": datetime.now().isoformat()
            }
        )
    
    async def _validate_policy_citation(
        self,
        policy_ref: str,
        policy_ids: Set[str],
        explanation: Dict[str, Any],
        citation_text: Optional[str] = None
    ) -> CitationValidation:
        """Validate a policy citation"""
        
        exists_in_corpus = policy_ref in policy_ids
        is_valid = exists_in_corpus
        
        status = CitationStatus.VALID if is_valid else CitationStatus.INVALID
        
        return CitationValidation(
            citation_id=f"pol-{policy_ref}",
            citation_type="policy",
            reference_id=policy_ref,
            reference_text=citation_text or f"Policy {policy_ref}",
            exists_in_bundle=True,  # Policies are always in corpus
            exists_in_corpus=exists_in_corpus,
            is_valid=is_valid,
            status=status,
            validation_details={
                "explanation_point": explanation.get('point_number'),
                "detector": explanation.get('detector_name'),
                "validated_at": datetime.now().isoformat()
            }
        )
    
    def _get_evidence_ids(self, evidence_bundle: Dict[str, Any]) -> Set[str]:
        """Extract all evidence IDs from bundle"""
        
        evidence_ids = set()
        
        # From evidence list
        for evidence in evidence_bundle.get('evidence', []):
            if evidence.get('id'):
                evidence_ids.add(evidence['id'])
        
        # From signals
        for signal in evidence_bundle.get('signals', []):
            if signal.get('evidence_ids'):
                evidence_ids.update(signal['evidence_ids'])
        
        # From bundle metadata
        if evidence_bundle.get('evidence_ids'):
            evidence_ids.update(evidence_bundle['evidence_ids'])
        
        return evidence_ids
    
    def _get_policy_ids(self, retrieved_policies: List[Dict[str, Any]]) -> Set[str]:
        """Extract all policy IDs from retrieved policies"""
        
        policy_ids = set()
        
        for policy in retrieved_policies:
            if policy.get('policy_id'):
                policy_ids.add(policy['policy_id'])
            elif policy.get('id'):
                policy_ids.add(policy['id'])
        
        return policy_ids
    
    def get_citation_summary(
        self,
        validations: List[CitationValidation]
    ) -> Dict[str, Any]:
        """Get summary of citation validations"""
        
        total = len(validations)
        valid = sum(1 for v in validations if v.is_valid)
        invalid = total - valid
        
        return {
            "total_citations": total,
            "valid_citations": valid,
            "invalid_citations": invalid,
            "validity_percentage": (valid / total * 100) if total > 0 else 0,
            "evidence_citations": sum(1 for v in validations if v.citation_type == "evidence"),
            "policy_citations": sum(1 for v in validations if v.citation_type == "policy")
        }