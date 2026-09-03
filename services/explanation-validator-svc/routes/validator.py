from fastapi import APIRouter, Request, HTTPException, status
from typing import Optional
from models.validation import ValidationRequest, ExplanationValidationResult

router = APIRouter(prefix="/api/v1/validator", tags=["validator"])

@router.post("/validate", response_model=ExplanationValidationResult)
async def validate_explanation(
    request: ValidationRequest,
    req: Request,
):
    """Validate an explanation"""
    
    validator_service = req.app.state.validator_service
    user = getattr(req.state, 'user', None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        result = await validator_service.validate(request)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/result/{validation_id}")
async def get_validation_result(
    validation_id: str,
    req: Request,
):
    """Get validation result by ID"""
    
    validator_service = req.app.state.validator_service
    user = getattr(req.state, 'user', None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    result = await validator_service.get_validation_result(validation_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Validation result not found"
        )
    
    return result

@router.get("/stats")
async def get_validation_stats(
    req: Request,
):
    """Get validation statistics"""
    
    validator_service = req.app.state.validator_service
    user = getattr(req.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view stats"
        )
    
    async with validator_service.db_pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_validations,
                SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed,
                SUM(CASE WHEN status = 'grounded' THEN 1 ELSE 0 END) as grounded,
                SUM(CASE WHEN status = 'ungrounded' THEN 1 ELSE 0 END) as ungrounded,
                SUM(CASE WHEN status = 'masked' THEN 1 ELSE 0 END) as masked,
                AVG(grounding_score) as avg_grounding_score,
                AVG(citation_coverage) as avg_citation_coverage
            FROM explanation_validations
        """)
        
        return dict(stats)