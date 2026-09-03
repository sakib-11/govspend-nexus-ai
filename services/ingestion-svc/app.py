"""Ingestion Service - L0"""
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from datetime import datetime

from libs.shared.config import get_settings
from libs.shared.models import CanonicalTransaction, IngestResponse
from libs.crypto.tokenizer import Tokenizer

settings = get_settings()
app = FastAPI(
    title="Ingestion Service",
    description="L0 - Data Ingestion for GovSpend Nexus AI",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize tokenizer
tokenizer = Tokenizer(settings.HMAC_KEY)

@app.get("/")
async def root():
    return {
        "service": "ingestion-svc",
        "version": settings.APP_VERSION,
        "status": "running"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ingestion-svc"}

@app.post("/ingest/invoice")
async def ingest_invoice(
    file: UploadFile = File(...),
    department_id: str = "DEPT-001",
    region: str = "MH-07"
):
    """Ingest an invoice file"""
    try:
        # Read file
        content = await file.read()
        
        # Mock extraction (replace with real OCR)
        extracted = {
            "vendor_gst": "22AAACF1234A1Z5",
            "amount": 125000.00,
            "unit_price": 2500.00,
            "quantity": 50,
            "category": "office_supplies",
            "approver": "OFF-12345"
        }
        
        # Tokenize vendor
        vendor_token = tokenizer.tokenize(
            extracted.get("vendor_gst", "unknown"),
            "VEND"
        )
        
        # Create transaction
        txn = CanonicalTransaction(
            invoice_doc_hash="mock_hash",
            vendor_token=vendor_token,
            department_id=department_id,
            amount=extracted.get("amount", 0.0),
            unit_price=extracted.get("unit_price", 0.0),
            quantity=extracted.get("quantity", 1),
            category=extracted.get("category", "general"),
            region=region,
            submitted_at=datetime.utcnow(),
            source="Manual",
            approver_token=extracted.get("approver")
        )
        
        return IngestResponse(
            transaction_id=txn.id,
            status="ingested",
            vendor_token=vendor_token,
            message="Invoice ingested successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.API_HOST,
        port=settings.PORT_INGESTION
    )
