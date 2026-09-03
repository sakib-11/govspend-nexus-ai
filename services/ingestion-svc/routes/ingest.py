"""Invoice upload and ingestion routes."""

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
from pathlib import Path

from ..models.invoice import InvoiceData, UploadResponse
from ..utils.validators import FileValidator
from ..services.storage import StorageService
from ..ocr.core import OCRService
from ..ocr.extractors.invoice_extractor import InvoiceDataExtractor
from ..utils.logging import get_logger

router = APIRouter(prefix="/ingest", tags=["Ingestion"])
logger = get_logger(__name__)

def get_ocr_service(request: Request) -> OCRService:
    """Dependency for OCR service."""
    return request.app.state.ocr_service

def get_storage_service(request: Request) -> StorageService:
    """Dependency for storage service."""
    return request.app.state.storage

@router.post("/invoice", response_model=UploadResponse)
async def upload_invoice(
    request: Request,
    file: UploadFile = File(..., description="Invoice PDF or image file"),
    extract_metadata: bool = True,
    ocr_service: OCRService = Depends(get_ocr_service),
    storage: StorageService = Depends(get_storage_service),
):
    """
    Upload and process an invoice document.
    """
    start_time = datetime.now()
    upload_id = str(uuid.uuid4())
    
    try:
        # Step 1: Validate file
        validator = FileValidator()
        validation = await validator.validate(file)
        
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail={"errors": validation["errors"]}
            )
        
        # Step 2: Save file temporarily
        temp_path = await storage.save_temp_file(
            file=file,
            upload_id=upload_id,
            original_filename=file.filename
        )
        
        logger.info(f"Processing file: {file.filename} (upload_id: {upload_id})")
        
        # Step 3: Process with OCR
        ocr_result = await ocr_service.process_document(
            file_path=temp_path,
            content_type=file.content_type or "application/pdf"
        )
        
        # Step 4: Extract invoice data
        invoice_data = None
        extracted_fields = None
        
        if extract_metadata and ocr_result.extracted_fields:
            extracted_fields = ocr_result.extracted_fields
            try:
                # Try to parse into structured invoice data
                extractor = InvoiceDataExtractor()
                invoice_data = extractor.extract_from_fields(ocr_result.extracted_fields)
            except Exception as e:
                logger.warning(f"Failed to extract structured invoice data: {str(e)}")
        
        # Step 5: Move to processed
        await storage.move_to_processed(
            temp_path=temp_path,
            upload_id=upload_id,
            ocr_result=ocr_result.to_dict()
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Step 6: Return response
        return UploadResponse(
            upload_id=upload_id,
            filename=file.filename,
            status="success",
            processing_time_seconds=processing_time,
            invoice_data=invoice_data,
            ocr_confidence=ocr_result.confidence,
            ocr_engine=ocr_result.engine,
            page_count=ocr_result.page_count,
            warnings=ocr_result.warnings,
            extracted_fields=extracted_fields
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing upload {upload_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process invoice: {str(e)}"
        )

@router.get("/status/{upload_id}")
async def get_upload_status(
    upload_id: str,
    storage: StorageService = Depends(get_storage_service),
):
    """Get status of a previously uploaded invoice."""
    status = await storage.get_upload_status(upload_id)
    if not status:
        raise HTTPException(status_code=404, detail="Upload not found")
    return status


# Add to services/ingestion-svc/routes/ingest.py

from ..ocr.pipeline import ExtractionPipeline

@router.post("/invoice/extract", response_model=UploadResponse)
async def extract_invoice(
    request: Request,
    file: UploadFile = File(...),
    validate_fields: bool = True,
    ocr_service: OCRService = Depends(get_ocr_service),
    storage: StorageService = Depends(get_storage_service),
):
    """Upload and extract invoice data."""
    start_time = datetime.now()
    upload_id = str(uuid.uuid4())
    
    try:
        # Process OCR
        temp_path = await storage.save_temp_file(file, upload_id, file.filename)
        ocr_result = await ocr_service.process_document(temp_path)
        
        # Run extraction pipeline
        pipeline = ExtractionPipeline()
        extraction_result = await pipeline.process(
            ocr_result=ocr_result,
            upload_id=upload_id,
            validate=validate_fields
        )
        
        # Return results
        return {
            "upload_id": upload_id,
            "filename": file.filename,
            "status": "success",
            "processing_time_seconds": (datetime.now() - start_time).total_seconds(),
            "extraction": extraction_result,
            "invoice_data": extraction_result.get("invoice_data")
        }
        
    except Exception as e:
        logger.error(f"Extraction failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
