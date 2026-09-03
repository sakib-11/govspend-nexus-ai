"""Prompt routes — REST API for prompt generation, validation, and templates."""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status

from models.prompt import (
    LLMInput,
    PromptRequest,
    RiskTier,
    ValidateOutputRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/prompt", tags=["prompt"])


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_service(request: Request, name: str) -> Any:
    svc = getattr(request.app.state, name, None)
    if svc is None:
        raise HTTPException(status_code=503, detail=f"Service {name} unavailable")
    return svc


def _require_auth(request: Request) -> Any:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post("/generate")
async def generate_prompt(body: PromptRequest, request: Request) -> Dict[str, Any]:
    """Generate a system + user prompt pair for the LLM."""
    _require_auth(request)
    prompt_svc = _get_service(request, "prompt_service")

    try:
        result = await prompt_svc.generate_prompt(body)
        return result.model_dump(mode="json")
    except Exception as exc:
        logger.exception("Prompt generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/validate-input")
async def validate_input(body: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """Validate LLM input data against the schema."""
    _require_auth(request)
    prompt_svc = _get_service(request, "prompt_service")

    try:
        result = await prompt_svc.validate_input(body)
        return result.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/validate-output")
async def validate_output(body: ValidateOutputRequest, request: Request) -> Dict[str, Any]:
    """Validate LLM output data against the schema and check grounding."""
    _require_auth(request)
    prompt_svc = _get_service(request, "prompt_service")

    try:
        result = await prompt_svc.validate_output(body.output_data, body.input_data)
        return result.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/format-output")
async def format_output(body: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """Parse raw LLM JSON response into a validated structured output."""
    _require_auth(request)
    prompt_svc = _get_service(request, "prompt_service")

    try:
        result = await prompt_svc.format_output(body)
        return result.model_dump(mode="json")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid output format: {exc}")


@router.get("/templates")
async def get_templates(request: Request) -> Dict[str, Any]:
    """List available prompt templates and styles."""
    _require_auth(request)
    prompt_svc = _get_service(request, "prompt_service")
    return prompt_svc.get_available_templates()


@router.post("/test")
async def test_prompt(request: Request) -> Dict[str, Any]:
    """Generate a prompt from sample data (for testing / prototyping)."""
    _require_auth(request)
    prompt_svc = _get_service(request, "prompt_service")

    sample_input = LLMInput(
        case_id="TEST-001",
        transaction_id="TX-001",
        risk_score=0.85,
        risk_tier=RiskTier.HIGH,
        evidence_bundle={
            "evidence": [
                {"id": "EV-001", "description": "Invoice unit price 50% above market"},
                {"id": "EV-002", "description": "Near-duplicate transaction in vendor history"},
            ],
        },
        retrieved_policies=[
            {"policy_id": "GFR-4.3", "title": "Procurement Pricing Rules",
             "content": "All procurement must be at prevailing market rates.", "relevance": 0.9},
        ],
        signals=[
            {"detector_type": "price_deviation", "signal_value": 0.92, "confidence": 0.95,
             "evidence_ids": ["EV-001"]},
            {"detector_type": "duplicate_fuzzy", "signal_value": 0.80, "confidence": 0.90,
             "evidence_ids": ["EV-002"]},
        ],
        metadata={"department": "Public Works", "amount": 150000.00, "vendor_token": "VEND-ABC"},
    )

    req = PromptRequest(llm_input=sample_input, include_few_shot=True)
    result = await prompt_svc.generate_prompt(req)
    return result.model_dump(mode="json")


@router.post("/generate-and-validate")
async def generate_and_validate(body: Dict[str, Any], request: Request) -> Dict[str, Any]:
    """Generate a prompt and validate a provided output in one call."""
    _require_auth(request)
    prompt_svc = _get_service(request, "prompt_service")

    try:
        prompt_req_data = body.get("prompt_request")
        output_data = body.get("output_data")

        if not prompt_req_data:
            raise HTTPException(status_code=400, detail="prompt_request is required")

        prompt_req = PromptRequest(**prompt_req_data)
        result = await prompt_svc.generate_with_validation(prompt_req, output_data)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("generate-and-validate failed")
        raise HTTPException(status_code=500, detail=str(exc))
