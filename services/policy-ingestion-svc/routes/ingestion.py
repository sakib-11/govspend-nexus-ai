from fastapi import APIRouter, Request, HTTPException, status, UploadFile, File, Form
from typing import Optional, List
from pathlib import Path
import tempfile
import os
from services.ingestion_service import IngestionService
from models.policy import PolicyDocument, PolicyCategory

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])

@router.post("/file")
async def ingest_file(
    request: Request,
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """Ingest a single policy document file"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can ingest documents"
        )
    
    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    # Save temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        # Build metadata
        metadata = {
            "title": title or Path(file.filename).stem,
            "category": category or "regulatory",
            "description": description,
            "uploaded_by": user.user_id,
            "original_filename": file.filename
        }
        
        # Ingest
        ingestion_service = request.app.state.ingestion_service
        result = await ingestion_service.ingest_file(tmp_file_path, metadata)
        
        return {
            "status": "success",
            "document": result["document"],
            "chunks_created": result["chunks"],
            "embeddings_generated": result["embeddings"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    finally:
        # Clean up temp file
        if os.path.exists(tmp_file_path):
            os.unlink(tmp_file_path)

@router.post("/directory")
async def ingest_directory(
    request: Request,
    directory_path: str,
    category: Optional[str] = None
):
    """Ingest all documents in a directory"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can ingest documents"
        )
    
    metadata = {
        "category": category or "regulatory",
        "ingested_by": user.user_id
    }
    
    ingestion_service = request.app.state.ingestion_service
    result = await ingestion_service.ingest_directory(directory_path, metadata)
    
    return {
        "status": "completed",
        "total": result["total"],
        "success": result["success"],
        "failed": result["failed"],
        "errors": result["errors"]
    }

@router.get("/documents")
async def list_documents(
    request: Request,
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0
):
    """List ingested documents"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view documents"
        )
    
    async with request.app.state.db_pool.acquire() as conn:
        conditions = []
        params = []
        param_idx = 1
        
        if category:
            conditions.append(f"category = ${param_idx}")
            params.append(category)
            param_idx += 1
        
        if active_only:
            conditions.append("is_active = TRUE")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        rows = await conn.fetch(f"""
            SELECT * FROM policy_documents
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """, *params, limit, offset)
        
        return {
            "documents": [dict(row) for row in rows],
            "total": len(rows),
            "limit": limit,
            "offset": offset
        }

@router.get("/stats")
async def get_stats(
    request: Request
):
    """Get ingestion statistics"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view statistics"
        )
    
    ingestion_service = request.app.state.ingestion_service
    stats = await ingestion_service.get_ingestion_stats()
    
    return stats

@router.delete("/document/{document_id}")
async def delete_document(
    document_id: str,
    request: Request
):
    """Delete a document and its chunks"""
    
    user = getattr(request.state, 'user', None)
    if not user or not user.is_super_admin():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete documents"
        )
    
    ingestion_service = request.app.state.ingestion_service
    
    # Delete from vector store
    await ingestion_service.vector_store.delete_document(document_id)
    
    # Delete from database
    async with request.app.state.db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM policy_documents
            WHERE document_id = $1
        """, document_id)
    
    return {"status": "deleted", "document_id": document_id}
