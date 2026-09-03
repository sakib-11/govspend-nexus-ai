from typing import Dict, Any, Optional, List
import httpx
from models.validation import ValidationStatus
from config import ValidatorConfig
import logging

logger = logging.getLogger(__name__)

class RephraserService:
    """Service for rephrasing ungrounded claims using LLM"""
    
    def __init__(self, config: ValidatorConfig):
        self.config = config
        self.enabled = config.rephraser_enabled
        self.model = config.rephraser_model
        self.max_attempts = config.rephraser_max_attempts
        
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def rephrase_ungrounded_claims(
        self,
        explanation: Dict[str, Any],
        ungrounded_claims: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Rephrase ungrounded claims to make them grounded"""
        
        if not self.enabled or not ungrounded_claims:
            return explanation
        
        rephrased_explanation = explanation.copy()
        
        for idx, claim in enumerate(ungrounded_claims):
            # Get the explanation point index
            point_idx = claim.get('explanation_index', 0)
            if point_idx >= len(rephrased_explanation.get('explanations', [])):
                continue
            
            exp_point = rephrased_explanation['explanations'][point_idx]
            
            # Rephrase the sentence
            rephrased = await self._rephrase_sentence(
                exp_point.get('sentence', ''),
                claim
            )
            
            if rephrased:
                exp_point['sentence'] = rephrased
                exp_point['rephrased'] = True
                exp_point['rephrased_claims'] = [
                    claim.get('claim_value', '')
                    for claim in ungrounded_claims
                    if claim.get('explanation_index') == point_idx
                ]
        
        return rephrased_explanation
    
    async def _rephrase_sentence(
        self,
        sentence: str,
        claim: Dict[str, Any]
    ) -> Optional[str]:
        """Rephrase a single sentence"""
        
        # Build prompt for rephrasing
        prompt = f"""
        Rephrase the following sentence to remove ungrounded claims while maintaining meaning:
        
        Original: {sentence}
        
        Ungrounded claim: {claim.get('claim_value', 'unknown')}
        
        Provide a rephrased version that acknowledges uncertainty or removes the specific claim.
        """
        
        try:
            # Use Groq or OpenAI to rephrase
            response = await self.client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant that rephrases sentences to remove ungrounded claims."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 200
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                rephrased = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                return rephrased.strip()
            
        except Exception as e:
            logger.error(f"Rephraser error: {e}")
        
        return None
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()