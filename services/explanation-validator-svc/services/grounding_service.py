from typing import List, Dict, Any, Optional, Set
import re
from models.validation import GroundingCheck, ValidationStatus
from datetime import datetime

class GroundingService:
    """Service for checking grounding of explanations"""
    
    def __init__(self):
        self._evidence_patterns = self._load_evidence_patterns()
        self._policy_patterns = self._load_policy_patterns()
    
    def _load_evidence_patterns(self) -> List[Dict[str, Any]]:
        """Load patterns for evidence references"""
        return [
            {
                "pattern": r'EV-\d+',
                "type": "evidence_id",
                "description": "Evidence ID pattern"
            },
            {
                "pattern": r'evidence\s+([A-Z0-9\-]+)',
                "type": "evidence_reference",
                "description": "Evidence reference pattern"
            }
        ]
    
    def _load_policy_patterns(self) -> List[Dict[str, Any]]:
        """Load patterns for policy references"""
        return [
            {
                "pattern": r'GFR-\d+\.\d+',
                "type": "policy_id",
                "description": "GFR policy pattern"
            },
            {
                "pattern": r'Section\s+(\d+\.\d+)',
                "type": "policy_section",
                "description": "Policy section pattern"
            },
            {
                "pattern": r'policy\s+([A-Z0-9\-\.]+)',
                "type": "policy_reference",
                "description": "Policy reference pattern"
            }
        ]
    
    async def check_grounding(
        self,
        explanation: Dict[str, Any],
        evidence_bundle: Dict[str, Any],
        retrieved_policies: List[Dict[str, Any]]
    ) -> List[GroundingCheck]:
        """Check grounding of all claims in explanation"""
        
        grounding_checks = []
        
        # Check each explanation point
        for exp in explanation.get('explanations', []):
            sentence = exp.get('sentence', '')
            
            # Check evidence grounding
            evidence_check = await self._check_evidence_grounding(
                sentence,
                exp.get('evidence_ids', []),
                evidence_bundle
            )
            grounding_checks.append(evidence_check)
            
            # Check policy grounding
            policy_check = await self._check_policy_grounding(
                sentence,
                exp.get('policy_references', []),
                retrieved_policies
            )
            grounding_checks.append(policy_check)
            
            # Check citations grounding
            for citation in exp.get('citations', []):
                citation_check = await self._check_citation_grounding(
                    citation,
                    evidence_bundle,
                    retrieved_policies
                )
                grounding_checks.append(citation_check)
        
        return grounding_checks
    
    async def _check_evidence_grounding(
        self,
        sentence: str,
        evidence_ids: List[str],
        evidence_bundle: Dict[str, Any]
    ) -> GroundingCheck:
        """Check if evidence claims are grounded"""
        
        # Get all evidence IDs from bundle
        available_evidence = self._get_available_evidence(evidence_bundle)
        
        # Check each evidence ID
        grounded_evidence = [eid for eid in evidence_ids if eid in available_evidence]
        ungrounded_evidence = [eid for eid in evidence_ids if eid not in available_evidence]
        
        is_grounded = len(ungrounded_evidence) == 0
        
        return GroundingCheck(
            check_id=f"evid-{datetime.now().timestamp()}",
            claim_type="evidence",
            claim_value=", ".join(evidence_ids) if evidence_ids else "No evidence",
            is_grounded=is_grounded,
            source_id=",".join(grounded_evidence) if grounded_evidence else None,
            source_type="evidence_bundle",
            confidence=len(grounded_evidence) / len(evidence_ids) if evidence_ids else 0,
            details={
                "total_evidence": len(evidence_ids),
                "grounded_count": len(grounded_evidence),
                "ungrounded_count": len(ungrounded_evidence),
                "available_evidence": list(available_evidence)[:10]
            },
            status=ValidationStatus.GROUNDED if is_grounded else ValidationStatus.UNGROUNDED
        )
    
    async def _check_policy_grounding(
        self,
        sentence: str,
        policy_refs: List[str],
        retrieved_policies: List[Dict[str, Any]]
    ) -> GroundingCheck:
        """Check if policy claims are grounded"""
        
        # Get all policy IDs from retrieved policies
        available_policies = self._get_available_policies(retrieved_policies)
        
        # Check each policy reference
        grounded_policies = [p for p in policy_refs if p in available_policies]
        ungrounded_policies = [p for p in policy_refs if p not in available_policies]
        
        is_grounded = len(ungrounded_policies) == 0
        
        return GroundingCheck(
            check_id=f"pol-{datetime.now().timestamp()}",
            claim_type="policy",
            claim_value=", ".join(policy_refs) if policy_refs else "No policies",
            is_grounded=is_grounded,
            source_id=",".join(grounded_policies) if grounded_policies else None,
            source_type="retrieved_policies",
            confidence=len(grounded_policies) / len(policy_refs) if policy_refs else 0,
            details={
                "total_policies": len(policy_refs),
                "grounded_count": len(grounded_policies),
                "ungrounded_count": len(ungrounded_policies),
                "available_policies": list(available_policies)[:10]
            },
            status=ValidationStatus.GROUNDED if is_grounded else ValidationStatus.UNGROUNDED
        )
    
    async def _check_citation_grounding(
        self,
        citation: Dict[str, Any],
        evidence_bundle: Dict[str, Any],
        retrieved_policies: List[Dict[str, Any]]
    ) -> GroundingCheck:
        """Check if a citation is grounded"""
        
        citation_type = citation.get('citation_type', 'evidence')
        reference_id = citation.get('reference_id', '')
        
        if citation_type == 'evidence':
            available = self._get_available_evidence(evidence_bundle)
            is_grounded = reference_id in available
            source_type = "evidence_bundle"
        else:
            available = self._get_available_policies(retrieved_policies)
            is_grounded = reference_id in available
            source_type = "retrieved_policies"
        
        return GroundingCheck(
            check_id=f"cit-{datetime.now().timestamp()}",
            claim_type=citation_type,
            claim_value=reference_id,
            is_grounded=is_grounded,
            source_id=reference_id if is_grounded else None,
            source_type=source_type,
            confidence=1.0 if is_grounded else 0.0,
            details={
                "citation_type": citation_type,
                "reference_text": citation.get('reference_text', ''),
                "available_count": len(available)
            },
            status=ValidationStatus.GROUNDED if is_grounded else ValidationStatus.UNGROUNDED
        )
    
    def _get_available_evidence(self, evidence_bundle: Dict[str, Any]) -> Set[str]:
        """Get all available evidence IDs from bundle"""
        
        evidence_ids = set()
        
        # From evidence list
        for evidence in evidence_bundle.get('evidence', []):
            if evidence.get('id'):
                evidence_ids.add(evidence['id'])
        
        # From signals
        for signal in evidence_bundle.get('signals', []):
            if signal.get('evidence_ids'):
                evidence_ids.update(signal['evidence_ids'])
        
        return evidence_ids
    
    def _get_available_policies(self, retrieved_policies: List[Dict[str, Any]]) -> Set[str]:
        """Get all available policy IDs from retrieved policies"""
        
        policy_ids = set()
        
        for policy in retrieved_policies:
            if policy.get('policy_id'):
                policy_ids.add(policy['policy_id'])
            elif policy.get('id'):
                policy_ids.add(policy['id'])
        
        return policy_ids
    
    def calculate_grounding_score(
        self,
        grounding_checks: List[GroundingCheck]
    ) -> float:
        """Calculate overall grounding score"""
        
        if not grounding_checks:
            return 0.0
        
        grounded = sum(1 for check in grounding_checks if check.is_grounded)
        total = len(grounding_checks)
        
        return grounded / total if total > 0 else 0.0
    
    def get_ungrounded_claims(
        self,
        grounding_checks: List[GroundingCheck]
    ) -> List[GroundingCheck]:
        """Get all ungrounded claims"""
        
        return [check for check in grounding_checks if not check.is_grounded]